from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import UserFactory
from .models import User


class ProfileTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory(username="alex", biography="Learning Python.")
        cls.teacher = UserFactory(username="morgan", role=User.Role.TEACHER)
        cls.inactive = UserFactory(is_active=False)

    def test_profile_routes_require_login(self):
        urls = [reverse("accounts:member-list"), reverse("accounts:profile-edit"),
                reverse("accounts:profile", args=[self.student.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url), f"{reverse('accounts:login')}?next={url}",
                )

    def test_both_roles_can_discover_members(self):
        admin = UserFactory(is_staff=True, is_superuser=True)
        for user in (self.student, self.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("accounts:member-list"))
                self.assertEqual(list(response.context["page"]), [self.student, self.teacher])
                self.assertNotContains(response, admin.username)
                self.assertContains(response, reverse("accounts:profile", args=[self.teacher.pk]))

    def test_profile_shows_shared_information_without_email(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        self.assertContains(response, self.student.get_full_name())
        self.assertContains(response, self.student.biography)
        self.assertNotContains(response, self.student.email)
        self.assertNotContains(response, self.student.password)
        self.assertNotContains(response, reverse("accounts:profile-edit"))

    def test_missing_and_inactive_profiles_return_404(self):
        self.client.force_login(self.student)
        for pk in (999999, self.inactive.pk):
            with self.subTest(pk=pk):
                response = self.client.get(reverse("accounts:profile", args=[pk]))
                self.assertEqual(response.status_code, 404)

    def test_edit_form_is_filled_with_own_details(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:profile-edit"))
        self.assertEqual(response.context["form"].initial["biography"], self.student.biography)

    def test_edit_updates_only_logged_in_account_and_allowed_fields(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("accounts:profile-edit"), {
            "first_name": "Alex", "last_name": "Wood", "biography": "Working on Django.",
            "id": self.teacher.pk, "username": self.teacher.username,
            "role": "teacher", "is_staff": True, "is_superuser": True,
            "email": "changed@example.com", "password": "changed",
        })
        self.assertRedirects(response, reverse("accounts:profile", args=[self.student.pk]))
        self.student.refresh_from_db()
        self.teacher.refresh_from_db()
        self.assertEqual(self.student.get_full_name(), "Alex Wood")
        self.assertEqual(self.student.biography, "Working on Django.")
        self.assertEqual(self.student.username, "alex")
        self.assertEqual(self.student.email, "alex@example.com")
        self.assertTrue(self.student.check_password("River-stone-482!"))
        self.assertEqual(self.student.role, User.Role.STUDENT)
        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertEqual(self.teacher.biography, "")
        self.assertEqual(self.teacher.first_name, "Jamie")

    def test_invalid_edit_does_not_change_profile(self):
        self.client.force_login(self.student)
        for data, field in [
            ({"first_name": "", "last_name": "Wood"}, "first_name"),
            ({"first_name": "Alex", "last_name": "Wood", "biography": "x" * 1001}, "biography"),
        ]:
            with self.subTest(field=field):
                response = self.client.post(reverse("accounts:profile-edit"), data)
                self.assertIn(field, response.context["form"].errors)
                self.student.refresh_from_db()
                self.assertEqual(self.student.biography, "Learning Python.")

    def test_profile_escapes_html_in_biography(self):
        self.student.biography = "<script>alert('hello')</script>"
        self.student.save()
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_member_directory_is_paginated(self):
        UserFactory.create_batch(25)
        self.client.force_login(self.student)
        first = self.client.get(reverse("accounts:member-list"))
        second = self.client.get(reverse("accounts:member-list"), {"page": 2})
        self.assertEqual(len(first.context["page"]), 25)
        self.assertEqual(len(second.context["page"]), 2)
        first_ids = {user.pk for user in first.context["page"]}
        second_ids = {user.pk for user in second.context["page"]}
        self.assertFalse(first_ids & second_ids)
