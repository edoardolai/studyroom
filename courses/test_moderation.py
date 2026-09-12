from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory, EnrolmentFactory, FeedbackFactory
from .models import CourseMaterial, Enrolment, Feedback


class StudentModerationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.enrolment = EnrolmentFactory(course=cls.course)
        cls.student = cls.enrolment.student
        cls.other_course = CourseFactory()
        cls.other_enrolment = EnrolmentFactory(course=cls.other_course, student=cls.student)
        cls.material = CourseMaterial.objects.create(course=cls.course, title="Exercise", file="exercise.pdf")
        FeedbackFactory(course=cls.course, student=cls.student)

    def action_url(self, action, course=None, enrolment=None):
        return reverse(f"courses:student-{action}", args=[
            (course or self.course).pk, (enrolment or self.enrolment).pk,
        ])

    def test_confirmation_get_does_not_change_enrolment(self):
        self.client.force_login(self.course.teacher)
        for action in ("remove", "block"):
            response = self.client.get(self.action_url(action))
            self.assertContains(response, f"Confirm {action}")
            self.assertContains(response, self.student.username)
        self.enrolment.refresh_from_db()
        self.assertFalse(self.enrolment.is_blocked)

    def test_removal_keeps_account_other_courses_and_feedback(self):
        self.client.force_login(self.course.teacher)
        response = self.client.post(self.action_url("remove"), {"student": self.other_course.teacher_id})
        self.assertRedirects(response, reverse("courses:roster", args=[self.course.pk]))
        self.assertFalse(Enrolment.objects.filter(pk=self.enrolment.pk).exists())
        self.assertTrue(Enrolment.objects.filter(pk=self.other_enrolment.pk).exists())
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertTrue(Feedback.objects.filter(course=self.course, student=self.student).exists())
        self.client.force_login(self.student)
        download = reverse("courses:material-download", args=[self.material.pk])
        self.assertEqual(self.client.get(download).status_code, 403)
        self.assertEqual(self.client.post(reverse("courses:enrol", args=[self.course.pk])).status_code, 302)
        self.assertTrue(Enrolment.objects.filter(course=self.course, student=self.student, is_blocked=False).exists())

    def test_block_revokes_access_and_prevents_reenrolment(self):
        self.client.force_login(self.course.teacher)
        self.client.post(self.action_url("block"))
        self.enrolment.refresh_from_db()
        self.assertTrue(self.enrolment.is_blocked)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse("courses:enrol", args=[self.course.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("courses:material-download", args=[self.material.pk])).status_code, 403)
        detail = self.client.get(reverse("courses:detail", args=[self.course.pk]))
        self.assertContains(detail, "You are blocked from this course.")
        self.assertNotContains(detail, "Enrol on this course")
        self.assertNotContains(detail, "Write or update your feedback")
        self.assertNotContains(detail, self.material.title)
        self.assertEqual(Enrolment.objects.filter(course=self.course, student=self.student).count(), 1)
        self.other_enrolment.refresh_from_db()
        self.assertFalse(self.other_enrolment.is_blocked)
        other = self.client.get(reverse("courses:detail", args=[self.other_course.pk]))
        self.assertTrue(other.context["has_access"])

    def test_blocked_course_is_absent_from_student_home_and_my_courses(self):
        Enrolment.objects.filter(pk=self.enrolment.pk).update(is_blocked=True)
        self.client.force_login(self.student)
        home = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        courses = self.client.get(reverse("courses:mine"))
        self.assertEqual(list(home.context["courses"]), [self.other_course])
        self.assertEqual(list(courses.context["page"]), [self.other_course])
        invalid_status = self.client.post(reverse("accounts:status-add"), {"body": ""})
        self.assertEqual(list(invalid_status.context["courses"]), [self.other_course])

    def test_unblock_requires_student_to_enrol_again(self):
        Enrolment.objects.filter(pk=self.enrolment.pk).update(is_blocked=True)
        self.client.force_login(self.course.teacher)
        self.assertContains(self.client.get(self.action_url("unblock")), "Confirm unblock")
        self.assertTrue(Enrolment.objects.get(pk=self.enrolment.pk).is_blocked)
        self.client.post(self.action_url("unblock"))
        self.assertFalse(Enrolment.objects.filter(pk=self.enrolment.pk).exists())
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("courses:material-download", args=[self.material.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("courses:enrol", args=[self.course.pk])).status_code, 302)
        self.assertTrue(Enrolment.objects.filter(course=self.course, student=self.student, is_blocked=False).exists())

    def test_only_course_teacher_can_moderate(self):
        for user, status in ((self.student, 403), (self.other_course.teacher, 404)):
            self.client.force_login(user)
            for action in ("remove", "block", "unblock"):
                with self.subTest(user=user.pk, action=action):
                    self.assertEqual(self.client.get(self.action_url(action)).status_code, status)
                    self.assertEqual(self.client.post(self.action_url(action)).status_code, status)
        self.enrolment.refresh_from_db()
        self.assertFalse(self.enrolment.is_blocked)

    def test_enrolment_id_must_belong_to_url_course(self):
        self.client.force_login(self.course.teacher)
        for action in ("remove", "block", "unblock"):
            response = self.client.post(self.action_url(action, enrolment=self.other_enrolment))
            self.assertEqual(response.status_code, 404)
        self.other_enrolment.refresh_from_db()
        self.assertFalse(self.other_enrolment.is_blocked)

    def test_moderation_requires_login(self):
        for action in ("remove", "block", "unblock"):
            self.assertEqual(self.client.post(self.action_url(action)).status_code, 302)
        self.enrolment.refresh_from_db()
        self.assertFalse(self.enrolment.is_blocked)

    def test_moderation_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.course.teacher)
        for action in ("remove", "block", "unblock"):
            self.assertEqual(client.post(self.action_url(action)).status_code, 403)
        self.enrolment.refresh_from_db()
        self.assertFalse(self.enrolment.is_blocked)
        client.get(self.action_url("block"))
        response = client.post(self.action_url("block"), {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.enrolment.refresh_from_db()
        self.assertTrue(self.enrolment.is_blocked)

    def test_stale_remove_cannot_lift_a_block(self):
        self.client.force_login(self.course.teacher)
        self.client.get(self.action_url("remove"))
        self.client.post(self.action_url("block"))
        self.assertEqual(self.client.post(self.action_url("remove")).status_code, 404)
        self.assertTrue(Enrolment.objects.get(pk=self.enrolment.pk).is_blocked)
        self.assertEqual(self.client.post(self.action_url("block")).status_code, 404)

    def test_unblock_cannot_remove_an_active_enrolment(self):
        self.client.force_login(self.course.teacher)
        self.assertEqual(self.client.post(self.action_url("unblock")).status_code, 404)
        self.assertTrue(Enrolment.objects.filter(pk=self.enrolment.pk).exists())

    def test_roster_separates_and_paginates_blocked_students(self):
        blocked = EnrolmentFactory.create_batch(26, course=self.course, is_blocked=True)
        self.client.force_login(self.course.teacher)
        url = reverse("courses:roster", args=[self.course.pk])
        first = self.client.get(url)
        second = self.client.get(url, {"blocked_page": 2})
        self.assertEqual(list(first.context["page"]), [self.enrolment])
        self.assertEqual(len(first.context["blocked"]), 25)
        self.assertEqual(len(second.context["blocked"]), 1)
        ids = {row.pk for row in first.context["blocked"]} | {row.pk for row in second.context["blocked"]}
        self.assertEqual(ids, {row.pk for row in blocked})

    def test_blocked_and_removed_student_cannot_change_existing_feedback(self):
        self.client.force_login(self.student)
        url = reverse("courses:feedback-edit", args=[self.course.pk])
        Enrolment.objects.filter(pk=self.enrolment.pk).update(is_blocked=True)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"body": "Changed"}).status_code, 403)
        self.enrolment.delete()
        self.assertEqual(self.client.post(url, {"body": "Changed"}).status_code, 403)
        self.assertEqual(Feedback.objects.get().body, "The exercises helped me understand joins.")
