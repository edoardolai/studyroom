import factory

from accounts.factories import UserFactory
from .models import Course, Enrolment, Feedback


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


class FeedbackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feedback

    course = factory.SubFactory(CourseFactory)
    student = factory.SubFactory(UserFactory)
    body = "The exercises helped me understand joins."
