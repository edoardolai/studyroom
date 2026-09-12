from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from kombu.exceptions import OperationalError
from pypdf import PdfWriter
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory, EnrolmentFactory
from .models import CourseMaterial, Notification
from .tasks import notify_material, queue_material_notification


class NotificationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.student = UserFactory()

    def test_new_enrolment_notifies_teacher_once(self):
        self.client.force_login(self.student)
        url = reverse("courses:enrol", args=[self.course.pk])
        self.client.post(url)
        self.client.post(url)
        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.course.teacher)
        self.assertEqual(notification.course, self.course)
        self.assertIn(self.student.username, notification.message)
        self.assertFalse(notification.is_read)

    def test_inbox_and_read_action_are_private(self):
        notification = Notification.objects.create(
            recipient=self.student, course=self.course, message="New practice material.",
        )
        inbox = reverse("courses:notifications")
        read = reverse("courses:notification-read", args=[notification.pk])
        self.assertEqual(self.client.get(inbox).status_code, 302)
        self.client.force_login(self.course.teacher)
        self.assertNotContains(self.client.get(inbox), notification.message)
        self.assertEqual(self.client.post(read).status_code, 404)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.student)
        response = client.get(inbox)
        self.assertContains(response, notification.message)
        self.assertEqual(response.context["unread_count"], 1)
        self.assertEqual(client.get(read).status_code, 405)
        self.assertEqual(client.post(read).status_code, 403)
        client.post(read, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(client.get(inbox).context["unread_count"], 0)

    def test_material_upload_queues_after_commit_and_notifies_eligible_students(self):
        EnrolmentFactory(course=self.course, student=self.student)
        EnrolmentFactory(course=self.course, is_blocked=True)
        EnrolmentFactory(course=self.course, student=UserFactory(is_active=False))
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)
        self.client.force_login(self.course.teacher)
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            with patch("courses.tasks.notify_material.delay") as delay:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(reverse("courses:material-upload", args=[self.course.pk]), {
                        "title": "Practice", "file": SimpleUploadedFile("practice.pdf", output.getvalue()),
                    })
                    self.assertEqual(response.status_code, 302)
                    delay.assert_not_called()
                material = CourseMaterial.objects.get()
                delay.assert_called_once_with(material.pk)
            EnrolmentFactory(course=self.course)
            notify_material.run(material.pk)
            notify_material.run(material.pk)
            notification = Notification.objects.get()
            self.assertEqual(notification.recipient, self.student)
            self.assertEqual(notification.material, material)
            self.assertIn("Practice", notification.message)

    def test_unavailable_broker_creates_material_notice_directly(self):
        EnrolmentFactory(course=self.course, student=self.student)
        material = CourseMaterial.objects.create(course=self.course, title="Practice", file="practice.pdf")
        with patch("courses.tasks.notify_material.delay", side_effect=OperationalError("Broker unavailable")):
            with self.assertLogs("courses.tasks", level="WARNING"):
                queue_material_notification(material.pk)
        self.assertEqual(Notification.objects.get().recipient, self.student)
