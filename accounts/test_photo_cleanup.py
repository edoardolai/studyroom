from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .factories import UserFactory


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
