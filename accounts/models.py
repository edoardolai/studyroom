from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import validate_photo


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"

    role = models.CharField(max_length=7, choices=Role.choices, default=Role.STUDENT)
    biography = models.TextField(max_length=1000, blank=True)
    photo = models.ImageField(
        upload_to="profiles/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"]), validate_photo],
        help_text="JPEG or PNG, up to 2 MB and 4096 by 4096 pixels.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["student", "teacher"]),
                name="user_valid_role",
            ),
        ]
