from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from PIL import Image

from .factories import StatusUpdateFactory, UserFactory
from .models import StatusUpdate, User


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

    def photo(self, name="photo.png", format="PNG", size=(16, 16)):
        output = BytesIO()
        Image.new("RGB", size, color="green").save(output, format=format)
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

    def test_raw_media_url_is_not_served(self):
        self.edit(photo=self.photo())
        self.student.refresh_from_db()
        self.assertEqual(self.client.get(self.student.photo.url).status_code, 404)

    def test_renamed_non_image_is_rejected(self):
        upload = SimpleUploadedFile("photo.png", b"not an image", content_type="image/png")
        response = self.edit(photo=upload)
        self.assertIn("photo", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertFalse(self.student.photo)

    def test_gif_renamed_as_png_is_rejected(self):
        response = self.edit(photo=self.photo(format="GIF"))
        self.assertIn("photo", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertFalse(self.student.photo)

    def test_image_with_unsupported_extension_is_rejected(self):
        response = self.edit(photo=self.photo(name="photo.html"))
        self.assertIn("photo", response.context["form"].errors)

    def test_oversized_file_is_rejected(self):
        data = self.photo().read() + b"x" * (2 * 1024 * 1024)
        response = self.edit(photo=SimpleUploadedFile("large.png", data))
        self.assertIn("photo", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertFalse(self.student.photo)

    def test_oversized_dimensions_are_rejected(self):
        response = self.edit(photo=self.photo(size=(4097, 1)))
        self.assertIn("photo", response.context["form"].errors)

    def test_edit_without_upload_keeps_current_photo(self):
        self.edit(photo=self.photo())
        self.student.refresh_from_db()
        name = self.student.photo.name
        response = self.edit(biography="Changed biography.")
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.photo.name, name)

    def test_invalid_replacement_keeps_photo_and_other_profile_fields(self):
        self.edit(photo=self.photo())
        self.student.refresh_from_db()
        name = self.student.photo.name
        response = self.edit(biography="Should not save.", photo=self.photo(format="GIF"))
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.photo.name, name)
        self.assertEqual(self.student.biography, "Hello.")

    def test_remove_photo_stops_serving_it(self):
        self.edit(photo=self.photo())
        response = self.edit(remove_photo=True)
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.photo)
        response = self.client.get(reverse("accounts:profile-photo", args=[self.student.pk]))
        self.assertEqual(response.status_code, 404)

    def test_upload_and_remove_together_are_rejected(self):
        response = self.edit(photo=self.photo(), remove_photo=True)
        self.assertIn("photo", response.context["form"].errors)

    def test_photo_of_inactive_account_is_not_served(self):
        self.edit(photo=self.photo())
        self.student.is_active = False
        self.student.save()
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:profile-photo", args=[self.student.pk]))
        self.assertEqual(response.status_code, 404)

    def test_admin_photo_link_uses_authenticated_route(self):
        self.edit(photo=self.photo())
        self.client.force_login(UserFactory(is_staff=True, is_superuser=True))
        response = self.client.get(reverse("admin:accounts_user_change", args=[self.student.pk]))
        self.assertContains(response, reverse("accounts:profile-photo", args=[self.student.pk]))
        self.assertNotContains(response, "/media/profiles/")


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

    def test_status_form_only_appears_on_own_page(self):
        self.client.force_login(self.student)
        own = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        other = self.client.get(reverse("accounts:profile", args=[self.teacher.pk]))
        self.assertContains(own, reverse("accounts:status-add"))
        self.assertNotContains(other, reverse("accounts:status-add"))

    def test_blank_and_long_updates_are_rejected(self):
        self.client.force_login(self.student)
        for body in ("", "   \n ", "x" * 501):
            with self.subTest(length=len(body)):
                response = self.client.post(reverse("accounts:status-add"), {"body": body})
                self.assertIn("body", response.context["form"].errors)
                self.assertEqual(response.context["member"], self.student)
                self.assertFalse(StatusUpdate.objects.exists())

    def test_500_character_update_is_accepted(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("accounts:status-add"), {"body": "x" * 500})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(StatusUpdate.objects.get().body), 500)

    def test_anonymous_user_cannot_post(self):
        response = self.client.post(reverse("accounts:status-add"), {"body": "Hello"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(StatusUpdate.objects.exists())

    def test_get_request_cannot_post(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:status-add"), {"body": "Hello"})
        self.assertEqual(response.status_code, 405)
        self.assertFalse(StatusUpdate.objects.exists())

    def test_profile_lists_only_its_authors_updates_newest_first(self):
        older = StatusUpdateFactory(author=self.student, body="First update.")
        newer = StatusUpdateFactory(author=self.student, body="Second update.")
        other = StatusUpdateFactory(author=self.teacher, body="Teacher's update.")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        self.assertEqual(list(response.context["page"]), [newer, older])
        self.assertNotContains(response, other.body)

    def test_status_html_is_escaped(self):
        StatusUpdateFactory(author=self.student, body="<script>alert('hello')</script>")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("accounts:profile", args=[self.student.pk]))
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_history_is_paginated(self):
        updates = StatusUpdateFactory.create_batch(12, author=self.student)
        self.client.force_login(self.teacher)
        url = reverse("accounts:profile", args=[self.student.pk])
        first = self.client.get(url)
        second = self.client.get(url, {"page": 2})
        self.assertEqual(list(first.context["page"]), list(reversed(updates[2:])))
        self.assertEqual(list(second.context["page"]), list(reversed(updates[:2])))

    def test_invalid_post_keeps_existing_updates_visible(self):
        update = StatusUpdateFactory(author=self.student)
        self.client.force_login(self.student)
        response = self.client.post(reverse("accounts:status-add"), {"body": ""})
        self.assertEqual(list(response.context["page"]), [update])

    def test_deleting_author_removes_their_updates_only(self):
        StatusUpdateFactory(author=self.student)
        other = StatusUpdateFactory(author=self.teacher)
        self.student.delete()
        self.assertEqual(list(StatusUpdate.objects.all()), [other])


class ProfileCsrfTests(APITestCase):
    def test_profile_edits_and_status_posts_require_csrf(self):
        user = UserFactory()
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        cases = [
            ("accounts:profile-edit", {"first_name": "Alex", "last_name": "Wood"}),
            ("accounts:status-add", {"body": "A new update."}),
        ]
        for name, data in cases:
            with self.subTest(route=name):
                response = client.post(reverse(name), data)
                self.assertEqual(response.status_code, 403)
                client.get(reverse("accounts:profile-edit"))
                response = client.post(reverse(name), {
                    **data, "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                })
                self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Alex")
        self.assertEqual(user.status_updates.get().body, "A new update.")
