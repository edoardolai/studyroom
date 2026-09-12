from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

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

    def test_invalid_course_is_not_saved(self):
        self.client.force_login(self.teacher)
        for title, description in [("", "Practice"), ("x" * 151, "Practice"), ("SQL", " ")]:
            with self.subTest(title=title):
                response = self.client.post(reverse("courses:create"), {
                    "title": title, "description": description,
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(Course.objects.exists())

    def test_members_can_browse_courses(self):
        course = CourseFactory(teacher=self.teacher)
        for user in (self.student, self.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("courses:list"))
                self.assertContains(response, course.title)
                response = self.client.get(reverse("courses:detail", args=[course.pk]))
                self.assertContains(response, course.description)

    def test_course_pages_require_login(self):
        course = CourseFactory(teacher=self.teacher)
        for url in (reverse("courses:list"), reverse("courses:create"),
                    reverse("courses:detail", args=[course.pk])):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_course_model_rejects_student_owner(self):
        course = Course(title="SQL", description="Practice", teacher=self.student)
        with self.assertRaises(ValidationError):
            course.full_clean()

    def test_missing_course_returns_404(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("courses:detail", args=[99999])).status_code, 404)


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

    def test_enrolment_requires_login_and_post(self):
        url = reverse("courses:enrol", args=[self.course.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(Enrolment.objects.exists())

    def test_enrolment_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.student)
        url = reverse("courses:enrol", args=[self.course.pk])
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(Enrolment.objects.exists())
        client.get(reverse("courses:detail", args=[self.course.pk]))
        response = client.post(url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Enrolment.objects.count(), 1)

    def test_teacher_cannot_view_another_roster(self):
        self.client.force_login(self.other_course.teacher)
        response = self.client.get(reverse("courses:roster", args=[self.course.pk]))
        self.assertEqual(response.status_code, 404)

    def test_even_enrolled_student_cannot_view_roster(self):
        EnrolmentFactory(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses:roster", args=[self.course.pk]))
        self.assertEqual(response.status_code, 403)

    def test_teacher_roster_contains_only_own_course_students(self):
        enrolment = EnrolmentFactory(course=self.course, student=self.student)
        EnrolmentFactory(course=self.other_course)
        self.client.force_login(self.course.teacher)
        response = self.client.get(reverse("courses:roster", args=[self.course.pk]))
        self.assertEqual(list(response.context["page"]), [enrolment])
        self.assertNotContains(response, self.student.email)

    def test_my_courses_matches_each_role(self):
        EnrolmentFactory(course=self.course, student=self.student)
        for user in (self.student, self.course.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("courses:mine"))
                self.assertEqual(list(response.context["page"]), [self.course])

    def test_course_owner_cannot_be_deleted_while_course_exists(self):
        with self.assertRaises(ProtectedError):
            self.course.teacher.delete()
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_enrolment_model_rejects_teacher_as_student(self):
        enrolment = Enrolment(course=self.course, student=self.other_course.teacher)
        with self.assertRaises(ValidationError):
            enrolment.full_clean()
