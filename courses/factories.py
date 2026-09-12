import factory

from accounts.factories import UserFactory
from .models import Course


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    teacher = factory.SubFactory(UserFactory, role="teacher")
    title = factory.Sequence(lambda n: f"Course {n}")
    description = "Practical exercises and discussion."
