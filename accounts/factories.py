import factory

from .models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"student{n}")
    first_name = "Jamie"
    last_name = "Reed"
    email = factory.LazyAttribute(lambda user: f"{user.username}@example.com")
    # Login tests need a hashed password, just like a registered account.
    password = factory.django.Password("River-stone-482!")
