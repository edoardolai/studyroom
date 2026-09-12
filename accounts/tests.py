from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import UserFactory
from .models import User


class RegistrationTests(APITestCase):
    def payload(self, **overrides):
        data = {
            "username": "newstudent", "first_name": "Alex", "last_name": "Wood",
            "email": "alex@example.com",
            "password1": "River-stone-482!", "password2": "River-stone-482!",
        }
        data.update(overrides)
        return data

    def test_registration_stores_details_and_hashed_password(self):
        response = self.client.post(reverse("accounts:register"), self.payload())
        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(username="newstudent")
        self.assertEqual(user.get_full_name(), "Alex Wood")
        self.assertEqual(user.email, "alex@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password("River-stone-482!"))
        self.assertNotEqual(user.password, "River-stone-482!")

    def test_submitted_role_and_admin_flags_are_ignored(self):
        self.client.post(reverse("accounts:register"), self.payload(
            role="teacher", is_staff="True", is_superuser="True",
        ))
        user = User.objects.get(username="newstudent")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_invalid_input_does_not_create_account(self):
        cases = [
            ({"password2": "Different-password-72!"}, "password2"),
            ({"password1": "123", "password2": "123"}, "password2"),
            ({"email": "not-an-email"}, "email"),
            ({"first_name": ""}, "first_name"),
            ({"last_name": ""}, "last_name"),
            ({"username": ""}, "username"),
        ]
        for overrides, field in cases:
            with self.subTest(overrides=overrides):
                response = self.client.post(
                    reverse("accounts:register"), self.payload(**overrides),
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(User.objects.count(), 0)

    def test_duplicate_username_is_rejected(self):
        UserFactory(username="newstudent")
        response = self.client.post(reverse("accounts:register"), self.payload())
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)


class LoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory(username="alex")
        cls.teacher = UserFactory(username="morgan", role=User.Role.TEACHER)

    def test_both_roles_can_log_in(self):
        for user in (self.student, self.teacher):
            with self.subTest(role=user.role):
                self.client.logout()
                response = self.client.post(reverse("accounts:login"), {
                    "username": user.username, "password": "River-stone-482!",
                })
                self.assertRedirects(response, reverse("accounts:index"))
                self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_wrong_password_is_rejected(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": self.student.username, "password": "wrong",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.teacher)
        url = reverse("accounts:logout")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(url), reverse("accounts:index"))
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.get(reverse("accounts:student-list"))
        self.assertEqual(response.status_code, 302)


class StudentListTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory(username="alex", email="private@example.com")
        cls.second_student = UserFactory(username="sam")
        cls.teacher = UserFactory(username="morgan", role=User.Role.TEACHER)
        cls.inactive = UserFactory(is_active=False)

    def test_student_gets_403_even_with_staff_flag(self):
        for is_staff in (False, True):
            with self.subTest(is_staff=is_staff):
                self.student.is_staff = is_staff
                self.student.save()
                self.client.force_login(self.student)
                response = self.client.get(reverse("accounts:student-list"))
                self.assertEqual(response.status_code, 403)

    def test_teacher_sees_active_students_without_private_fields(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:student-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page"]), [self.student, self.second_student])
        self.assertNotContains(response, self.student.email)
        self.assertNotContains(response, self.student.password)


class UserModelTests(APITestCase):
    def test_invalid_role_is_rejected_by_database(self):
        # Roll back the failed insert before returning to the test transaction.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(username="invalid", role="other")
