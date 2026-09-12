from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory
from .models import Course


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
