from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory
from .models import Notification


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
