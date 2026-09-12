from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"

    role = models.CharField(max_length=7, choices=Role.choices, default=Role.STUDENT)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["student", "teacher"]),
                name="user_valid_role",
            ),
        ]
