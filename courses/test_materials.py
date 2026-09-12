from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter
from rest_framework.test import APITestCase

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

    def pdf(self):
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)
        return SimpleUploadedFile("notes.pdf", output.getvalue(), content_type="application/pdf")

    def image(self, name="diagram.png", image_format="PNG"):
        output = BytesIO()
        Image.new("RGB", (16, 16), color="blue").save(output, format=image_format)
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
