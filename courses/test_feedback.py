from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory, EnrolmentFactory, FeedbackFactory
from .models import Feedback


class FeedbackTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.student = UserFactory()
        EnrolmentFactory(course=cls.course, student=cls.student)
        cls.url = reverse("courses:feedback-edit", args=[cls.course.pk])
        cls.detail = reverse("courses:detail", args=[cls.course.pk])

    def test_feedback_uses_session_student_and_url_course(self):
        other = UserFactory()
        other_course = CourseFactory()
        self.client.force_login(self.student)
        response = self.client.post(self.url, {
            "body": "Useful exercises.", "student": other.pk, "course": other_course.pk,
        })
        self.assertRedirects(response, self.detail)
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.student, self.student)
        self.assertEqual(feedback.course, self.course)
        self.assertEqual(feedback.body, "Useful exercises.")

    def test_resubmission_updates_own_feedback_only(self):
        other = FeedbackFactory(course=self.course)
        self.client.force_login(self.student)
        self.client.post(self.url, {"body": "First thoughts."})
        original = Feedback.objects.get(student=self.student)
        self.client.post(self.url, {"body": "More practice would help.", "id": other.pk})
        original.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(Feedback.objects.count(), 2)
        self.assertEqual(original.body, "More practice would help.")
        self.assertEqual(other.body, "The exercises helped me understand joins.")
        self.assertContains(self.client.get(self.url), original.body)

    def test_invalid_feedback_preserves_existing_entry(self):
        entry = FeedbackFactory(course=self.course, student=self.student)
        self.client.force_login(self.student)
        for body in ("", "   ", "x" * 2001):
            with self.subTest(length=len(body)):
                response = self.client.post(self.url, {"body": body})
                self.assertTrue(response.context["form"].errors)
                entry.refresh_from_db()
                self.assertEqual(entry.body, "The exercises helped me understand joins.")

    def test_maximum_length_is_accepted(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, {"body": "x" * 2000}).status_code, 302)
        self.assertEqual(len(Feedback.objects.get().body), 2000)

    def test_teacher_and_unenrolled_student_cannot_write_feedback(self):
        for user in (self.course.teacher, UserFactory()):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, {"body": "Hello"}).status_code, 403)
        self.assertFalse(Feedback.objects.exists())

    def test_feedback_requires_login(self):
        for response in (self.client.get(self.url), self.client.post(self.url, {"body": "Hello"})):
            self.assertEqual(response.status_code, 302)
        self.assertFalse(Feedback.objects.exists())

    def test_feedback_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.student)
        self.assertEqual(client.post(self.url, {"body": "Useful"}).status_code, 403)
        self.assertFalse(Feedback.objects.exists())
        client.get(self.url)
        response = client.post(self.url, {
            "body": "Useful", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)

    def test_database_rejects_duplicate_feedback(self):
        FeedbackFactory(course=self.course, student=self.student)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FeedbackFactory(course=self.course, student=self.student)

    def test_feedback_model_rejects_teacher(self):
        entry = Feedback(course=self.course, student=self.course.teacher, body="Hello")
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_members_can_read_feedback_but_html_is_escaped(self):
        FeedbackFactory(course=self.course, student=self.student, body="<script>hello</script>")
        for user in (self.course.teacher, UserFactory()):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(self.detail)
                self.assertContains(response, "&lt;script&gt;hello&lt;/script&gt;")
                self.assertNotContains(response, "<script>")
                self.assertNotContains(response, "Write or update your feedback")

    def test_feedback_is_paginated_newest_first_and_stays_on_its_course(self):
        entries = FeedbackFactory.create_batch(11, course=self.course)
        FeedbackFactory()
        self.client.force_login(self.student)
        first = self.client.get(self.detail)
        second = self.client.get(self.detail, {"feedback_page": 2})
        self.assertEqual(list(first.context["feedback"]), list(reversed(entries[1:])))
        self.assertEqual(list(second.context["feedback"]), entries[:1])
