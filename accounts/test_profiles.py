from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from PIL import Image

from .factories import UserFactory
from .models import StatusUpdate, User


class ProfileTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory(username="alex", biography="Learning Python.")
        cls.teacher = UserFactory(username="morgan", role=User.Role.TEACHER)
        cls.inactive = UserFactory(is_active=False)

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


class ProfilePhotoTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory()
        cls.teacher = UserFactory(role=User.Role.TEACHER)

    def setUp(self):
        # Uploaded test files should never end up in the real media folder.
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.student)

    def photo(self, name="photo.png", format="PNG"):
        output = BytesIO()
        Image.new("RGB", (16, 16), color="green").save(output, format=format)
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

    def edit(self, **overrides):
        data = {"first_name": "Jamie", "last_name": "Reed", "biography": "Hello."}
        data.update(overrides)
        return self.client.post(reverse("accounts:profile-edit"), data)

    def test_jpeg_and_png_uploads_are_saved_and_served_to_members(self):
        for name, format in [("photo.png", "PNG"), ("photo.jpg", "JPEG")]:
            with self.subTest(format=format):
                upload = self.photo(name=name, format=format)
                expected = upload.read()
                upload.seek(0)
                response = self.edit(photo=upload)
                self.assertRedirects(response, reverse("accounts:profile", args=[self.student.pk]))
                self.student.refresh_from_db()
                self.assertTrue(self.student.photo.storage.exists(self.student.photo.name))
                self.client.force_login(self.teacher)
                response = self.client.get(reverse("accounts:profile-photo", args=[self.student.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(b"".join(response.streaming_content), expected)
                self.client.force_login(self.student)

    def test_photo_requires_login_even_with_known_url(self):
        self.edit(photo=self.photo())
        self.client.logout()
        url = reverse("accounts:profile-photo", args=[self.student.pk])
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_renamed_non_image_is_rejected(self):
        upload = SimpleUploadedFile("photo.png", b"not an image", content_type="image/png")
        response = self.edit(photo=upload)
        self.assertIn("photo", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertFalse(self.student.photo)


class StatusUpdateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = UserFactory()
        cls.teacher = UserFactory(role=User.Role.TEACHER)

    def test_both_roles_can_post_on_their_home_page(self):
        for user in (self.student, self.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.post(reverse("accounts:status-add"), {
                    "body": "Finished today's reading.",
                })
                self.assertRedirects(response, reverse("accounts:profile", args=[user.pk]))
                self.assertEqual(user.status_updates.get().body, "Finished today's reading.")

    def test_submitted_author_is_ignored(self):
        self.client.force_login(self.student)
        self.client.post(reverse("accounts:status-add"), {
            "body": "My own update.", "author": self.teacher.pk,
        })
        self.assertEqual(StatusUpdate.objects.get().author, self.student)
        self.assertFalse(self.teacher.status_updates.exists())

    def test_blank_and_long_updates_are_rejected(self):
        self.client.force_login(self.student)
        for body in ("", "   \n ", "x" * 501):
            with self.subTest(length=len(body)):
                response = self.client.post(reverse("accounts:status-add"), {"body": body})
                self.assertIn("body", response.context["form"].errors)
                self.assertEqual(response.context["member"], self.student)
                self.assertFalse(StatusUpdate.objects.exists())
