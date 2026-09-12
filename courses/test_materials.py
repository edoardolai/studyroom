from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from .factories import CourseFactory, EnrolmentFactory
from .models import CourseMaterial


class MaterialTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.other_course = CourseFactory()
        cls.student = UserFactory()
        cls.outsider = UserFactory()
        EnrolmentFactory(course=cls.course, student=cls.student)

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.course.teacher)

    def pdf(self, encrypted=False):
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        if encrypted:
            writer.encrypt("test-password")
        writer.write(output)
        return SimpleUploadedFile("notes.pdf", output.getvalue(), content_type="application/pdf")

    def image(self, name="diagram.png", image_format="PNG", size=(16, 16)):
        output = BytesIO()
        Image.new("RGB", size, color="blue").save(output, format=image_format)
        return SimpleUploadedFile(name, output.getvalue())

    def upload(self, file=None, **overrides):
        data = {"title": "Week one notes", "file": file if file is not None else self.pdf()}
        data.update(overrides)
        return self.client.post(reverse("courses:material-upload", args=[self.course.pk]), data)

    def test_teacher_uploads_valid_pdf_and_images_to_own_course(self):
        for file in (self.pdf(), self.image(), self.image("diagram.jpg", "JPEG")):
            with self.subTest(name=file.name):
                response = self.upload(file, course=self.other_course.pk)
                self.assertRedirects(response, reverse("courses:detail", args=[self.course.pk]))
        self.assertEqual(CourseMaterial.objects.count(), 3)
        self.assertEqual(set(CourseMaterial.objects.values_list("course_id", flat=True)), {self.course.pk})

    def test_upload_requires_title_and_file(self):
        for data in ({"title": "Notes"}, {"title": "", "file": self.pdf()}):
            with self.subTest(fields=list(data)):
                response = self.client.post(reverse("courses:material-upload", args=[self.course.pk]), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_other_teacher_cannot_upload(self):
        self.client.force_login(self.other_course.teacher)
        self.assertEqual(self.upload().status_code, 404)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_student_cannot_open_or_submit_upload_form(self):
        self.client.force_login(self.student)
        url = reverse("courses:material-upload", args=[self.course.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.upload().status_code, 403)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_upload_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.course.teacher)
        response = client.post(reverse("courses:material-upload", args=[self.course.pk]), {
            "title": "Notes", "file": self.pdf(),
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_invalid_file_types_are_rejected(self):
        files = [
            SimpleUploadedFile("notes.pdf", b"This is not a PDF"),
            SimpleUploadedFile("notes.pdf", b"%PDF-1.7\nBroken document\n%%EOF"),
            SimpleUploadedFile("page.html", b"<h1>Hello</h1>"),
            self.image(name="diagram.png", image_format="GIF"),
            self.image(name="diagram.jpg", image_format="PNG"),
        ]
        for file in files:
            with self.subTest(name=file.name):
                response = self.upload(file)
                self.assertIn("file", response.context["form"].errors)
                self.assertFalse(CourseMaterial.objects.exists())

    def test_encrypted_pdf_is_rejected(self):
        response = self.upload(self.pdf(encrypted=True))
        self.assertIn("file", response.context["form"].errors)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_oversized_material_is_rejected(self):
        file = SimpleUploadedFile("large.pdf", b"x" * (10 * 1024 * 1024 + 1))
        response = self.upload(file)
        self.assertIn("file", response.context["form"].errors)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_oversized_image_dimensions_are_rejected(self):
        response = self.upload(self.image(size=(4097, 1)))
        self.assertIn("file", response.context["form"].errors)

    def test_owner_and_enrolled_student_can_download_complete_file(self):
        file = self.pdf()
        expected = file.read()
        file.seek(0)
        self.upload(file)
        material = CourseMaterial.objects.get()
        for user in (self.course.teacher, self.student):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("courses:material-download", args=[material.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertIn("attachment", response.headers["Content-Disposition"])
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(b"".join(response.streaming_content), expected)

    def test_outsiders_cannot_download_even_with_material_id(self):
        self.upload()
        material = CourseMaterial.objects.get()
        for user in (self.outsider, self.other_course.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("courses:material-download", args=[material.pk]))
                self.assertEqual(response.status_code, 403)
                response = self.client.get(reverse("courses:detail", args=[self.course.pk]))
                self.assertNotContains(response, material.title)

    def test_anonymous_user_cannot_upload_or_download(self):
        self.upload()
        material = CourseMaterial.objects.get()
        self.client.logout()
        self.assertEqual(self.upload().status_code, 302)
        response = self.client.get(reverse("courses:material-download", args=[material.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CourseMaterial.objects.count(), 1)

    def test_student_loses_download_access_if_enrolment_is_deleted(self):
        self.upload()
        material = CourseMaterial.objects.get()
        self.student.enrolments.all().delete()
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses:material-download", args=[material.pk]))
        self.assertEqual(response.status_code, 403)

    def test_raw_media_path_is_not_served(self):
        self.upload()
        material = CourseMaterial.objects.get()
        self.assertEqual(self.client.get(material.file.url).status_code, 404)

    def test_missing_file_returns_404(self):
        self.upload()
        material = CourseMaterial.objects.get()
        material.file.storage.delete(material.file.name)
        response = self.client.get(reverse("courses:material-download", args=[material.pk]))
        self.assertEqual(response.status_code, 404)
