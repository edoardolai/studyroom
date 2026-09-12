from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from .factories import UserFactory
from .models import User


class PhotoCleanupTests(APITestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = UserFactory(photo=self.photo())
        self.old_name = self.user.photo.name
        self.storage = self.user.photo.storage

    def photo(self):
        output = BytesIO()
        Image.new("RGB", (16, 16), color="green").save(output, format="PNG")
        return SimpleUploadedFile("photo.png", output.getvalue(), content_type="image/png")

    def test_replacement_deletes_old_file_after_commit_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.user.photo = self.photo()
            self.user.save()
            self.assertTrue(self.storage.exists(self.old_name))
        self.assertFalse(self.storage.exists(self.old_name))
        self.assertTrue(self.storage.exists(self.user.photo.name))

    def test_profile_remove_deletes_file_after_commit(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("accounts:profile-edit"), {
                "first_name": "Alex", "last_name": "Wood", "remove_photo": True,
            })
            self.assertEqual(response.status_code, 302)
        self.assertFalse(self.storage.exists(self.old_name))
        self.user.refresh_from_db()
        self.assertFalse(self.user.photo)

    def test_account_deletion_also_cleans_up_photo(self):
        with self.captureOnCommitCallbacks(execute=True):
            User.objects.filter(pk=self.user.pk).delete()
        self.assertFalse(self.storage.exists(self.old_name))

    def test_other_users_photo_is_preserved(self):
        other = UserFactory(photo=self.photo())
        other_name = other.photo.name
        with self.captureOnCommitCallbacks(execute=True):
            self.user.photo = ""
            self.user.save()
        self.assertFalse(self.storage.exists(self.old_name))
        self.assertTrue(self.storage.exists(other_name))

    def test_shared_file_is_kept_until_last_reference_is_removed(self):
        other = UserFactory(photo=self.old_name)
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertTrue(self.storage.exists(self.old_name))
        with self.captureOnCommitCallbacks(execute=True):
            other.delete()
        self.assertFalse(self.storage.exists(self.old_name))

    def test_rollback_keeps_original_photo(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(ValueError):
                with transaction.atomic():
                    self.user.photo = ""
                    self.user.save()
                    raise ValueError("Cancel this edit")
        self.assertEqual(callbacks, [])
        self.user.refresh_from_db()
        self.assertEqual(self.user.photo.name, self.old_name)
        self.assertTrue(self.storage.exists(self.old_name))

    def test_save_of_another_field_does_not_remove_photo(self):
        self.user.photo = ""
        self.user.first_name = "Alex"
        with self.captureOnCommitCallbacks(execute=True):
            self.user.save(update_fields=["first_name"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.photo.name, self.old_name)
        self.assertTrue(self.storage.exists(self.old_name))

    def test_invalid_form_does_not_schedule_cleanup(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(reverse("accounts:profile-edit"), {
                "first_name": "", "last_name": "Wood", "remove_photo": True,
            })
            self.assertEqual(response.status_code, 200)
        self.assertEqual(callbacks, [])
        self.assertTrue(self.storage.exists(self.old_name))
