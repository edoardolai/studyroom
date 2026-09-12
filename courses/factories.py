import factory

from accounts.factories import UserFactory
from .models import Course, Enrolment


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    teacher = factory.SubFactory(UserFactory, role="teacher")
    title = factory.Sequence(lambda n: f"Course {n}")
    description = "Practical exercises and discussion."


class EnrolmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Enrolment

    course = factory.SubFactory(CourseFactory)
    student = factory.SubFactory(UserFactory)
