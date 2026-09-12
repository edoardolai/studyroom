from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .validators import validate_material


class Course(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="courses_taught",
        limit_choices_to={"role": "teacher"},
    )
    title = models.CharField(max_length=150)
    description = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError({"teacher": "The course owner must be a teacher."})


class Enrolment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrolments")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrolments",
        limit_choices_to={"role": "student"},
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["enrolled_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_course_student"),
        ]

    def __str__(self):
        return f"{self.student} — {self.course}"

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only students can enrol on a course."})


class CourseMaterial(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=150)
    file = models.FileField(
        upload_to="course_materials/", validators=[validate_material],
        help_text="PDF, JPEG or PNG, up to 10 MB. Images: at most 4096 by 4096 pixels.",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-pk"]

    def __str__(self):
        return self.title


class Feedback(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="feedback")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_feedback",
        limit_choices_to={"role": "student"},
    )
    body = models.TextField(max_length=2000)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_course_feedback"),
        ]

    def __str__(self):
        return f"{self.student} — {self.course}"

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only students can leave course feedback."})
