from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory, EnrolmentFactory
from .models import Course, Enrolment


class CourseTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = UserFactory(role="teacher")
        cls.student = UserFactory()

    def test_teacher_creates_course_as_owner(self):
        other = UserFactory(role="teacher")
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("courses:create"), {
            "title": "SQL practice", "description": "Working with joins.", "teacher": other.pk,
        })
        course = Course.objects.get()
        self.assertEqual(course.teacher, self.teacher)
        self.assertRedirects(response, reverse("courses:detail", args=[course.pk]))

    def test_student_cannot_open_or_submit_creation_form(self):
        self.client.force_login(self.student)
        url = reverse("courses:create")
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(url, {"title": "SQL", "description": "Practice"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Course.objects.exists())


class EnrolmentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.student = UserFactory()
        cls.other_course = CourseFactory()

    def test_student_enrols_themselves_only(self):
        other = UserFactory()
        self.client.force_login(self.student)
        response = self.client.post(reverse("courses:enrol", args=[self.course.pk]), {
            "student": other.pk, "course": self.other_course.pk,
        })
        self.assertRedirects(response, reverse("courses:detail", args=[self.course.pk]))
        enrolment = Enrolment.objects.get()
        self.assertEqual(enrolment.student, self.student)
        self.assertEqual(enrolment.course, self.course)

    def test_repeated_enrolment_does_not_duplicate_row(self):
        self.client.force_login(self.student)
        url = reverse("courses:enrol", args=[self.course.pk])
        self.client.post(url)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(Enrolment.objects.count(), 1)

    def test_database_rejects_duplicate_enrolment(self):
        EnrolmentFactory(course=self.course, student=self.student)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrolment.objects.create(course=self.course, student=self.student)

    def test_teachers_cannot_enrol(self):
        for teacher in (self.course.teacher, self.other_course.teacher):
            with self.subTest(teacher=teacher.pk):
                self.client.force_login(teacher)
                response = self.client.post(reverse("courses:enrol", args=[self.course.pk]))
                self.assertEqual(response.status_code, 403)
        self.assertFalse(Enrolment.objects.exists())

    def test_teacher_cannot_view_another_roster(self):
        self.client.force_login(self.other_course.teacher)
        response = self.client.get(reverse("courses:roster", args=[self.course.pk]))
        self.assertEqual(response.status_code, 404)

    def test_even_enrolled_student_cannot_view_roster(self):
        EnrolmentFactory(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses:roster", args=[self.course.pk]))
        self.assertEqual(response.status_code, 403)
