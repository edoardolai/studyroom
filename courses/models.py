from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


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
