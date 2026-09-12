from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .factories import UserFactory


class UserApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory(username="alex", photo="profiles/alex.png")
        cls.teacher = UserFactory(username="morgan", role="teacher")

    def test_member_list_requires_login_and_shows_only_shared_fields(self):
        UserFactory(is_active=False)
        UserFactory(is_superuser=True)
        url = reverse("user-api:list")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.student)
        response = self.client.get(url)
        self.assertEqual(response.data["count"], 2)
        first = response.data["results"][0]
        self.assertEqual(set(first), {"id", "username", "first_name", "last_name", "role", "biography", "photo"})
        self.assertEqual(first["photo"], f"http://testserver/members/{self.student.pk}/photo/")
        self.assertEqual(response.data["results"][1]["id"], self.teacher.pk)

    def test_member_detail_is_read_only_and_excludes_inactive_accounts(self):
        self.client.force_login(self.student)
        url = reverse("user-api:detail", args=[self.teacher.pk])
        response = self.client.get(url)
        self.assertEqual(response.data["username"], "morgan")
        self.assertNotIn("email", response.data)
        self.assertEqual(self.client.patch(url, {"biography": "Changed"}).status_code, 405)
        self.teacher.is_active = False
        self.teacher.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_me_updates_only_own_allowed_fields(self):
        self.client.force_login(self.student)
        url = reverse("user-api:me")
        response = self.client.patch(url, {
            "first_name": "Alex", "biography": "Practising Django.", "id": self.teacher.pk,
            "username": "morgan", "role": "teacher", "is_staff": True,
            "password": "Changed", "email": "changed@example.com",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.teacher.refresh_from_db()
        self.assertEqual(self.student.first_name, "Alex")
        self.assertEqual(self.student.biography, "Practising Django.")
        self.assertEqual(self.student.username, "alex")
        self.assertEqual(self.student.role, "student")
        self.assertFalse(self.student.is_staff)
        self.assertTrue(self.student.check_password("River-stone-482!"))
        self.assertEqual(response.data["email"], self.student.email)
        self.assertEqual(self.student.email, "alex@example.com")
        self.assertEqual(self.teacher.biography, "")

    def test_invalid_profile_patch_leaves_existing_data(self):
        self.client.force_login(self.student)
        for data in ({"first_name": " "}, {"last_name": ""}, {"biography": "x" * 1001}):
            with self.subTest(data=data):
                response = self.client.patch(reverse("user-api:me"), data, format="json")
                self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Jamie")
        self.assertEqual(self.student.biography, "")

    def test_session_patch_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.student)
        url = reverse("user-api:me")
        self.assertEqual(client.patch(url, {"biography": "Changed"}, format="json").status_code, 403)
        client.get(reverse("accounts:profile-edit"))
        response = client.patch(url, {"biography": "Changed"}, format="json",
                                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.biography, "Changed")
