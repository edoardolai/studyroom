"""Create a small demonstration dataset with python load_data.py.

Existing accounts, passwords and edited content are left in place.
"""
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "studyroom.settings")
django.setup()

from django.contrib.auth.hashers import make_password
from django.core.files import File
from accounts.models import StatusUpdate, User
from courses.models import ChatMessage, Course, CourseMaterial, Enrolment, Feedback, Notification


DEMO_PASSWORD = "password123!"


def demo_user(username, first_name, last_name, role):
    user, created = User.objects.get_or_create(username=username, defaults={
        "first_name": first_name, "last_name": last_name, "role": role,
        "email": f"{username}@example.com", "password": make_password(DEMO_PASSWORD),
    })
    if user.role != role:
        raise ValueError(f"{username} already exists with a different role; check the demo account.")
    print(f"{'Created' if created else 'Kept'} account: {username}")
    return user


def run():
    bob = demo_user("bob", "Bob", "", "student")
    alice = demo_user("alice", "Alice", "", "student")
    john = demo_user("john", "John", "", "student")
    grant = demo_user("grant", "Prof", "Grant", "teacher")
    mark = demo_user("mark", "Mark", "", "teacher")

    course, _ = Course.objects.get_or_create(teacher=grant, title="Database practice", defaults={
        "description": "Practise selecting, filtering and joining related tables.",
    })
    other_course, _ = Course.objects.get_or_create(teacher=mark, title="Web application design", defaults={
        "description": "Discuss forms, request handling and the structure of a Django application.",
    })
    Enrolment.objects.get_or_create(course=course, student=bob)
    Enrolment.objects.get_or_create(course=other_course, student=bob)
    Enrolment.objects.get_or_create(course=course, student=john)
    Enrolment.objects.get_or_create(course=other_course, student=alice, defaults={"is_blocked": True})

    StatusUpdate.objects.get_or_create(author=bob, body="Working through the joins exercise this week.")
    StatusUpdate.objects.get_or_create(author=alice, body="Reading about Django forms and validation.")
    Feedback.objects.get_or_create(course=course, student=bob, defaults={
        "body": "The exercise helped me understand the join. A three-table example would be useful next.",
    })
    ChatMessage.objects.get_or_create(course=course, author=bob, body="Should we join on the student ID?")
    ChatMessage.objects.get_or_create(course=course, author=grant, body="Yes. Match the student ID before selecting the columns.")

    material = CourseMaterial.objects.filter(course=course, title="Week one exercise").first()
    if material is None:
        material = CourseMaterial(course=course, title="Week one exercise")
        path = Path(__file__).resolve().parent / "demo_materials" / "joins_exercise.pdf"
        with path.open("rb") as source:
            material.file.save("joins_exercise.pdf", File(source))

    # Seed example notices directly: setup should not need a running worker.
    Notification.objects.get_or_create(recipient=grant, course=course, material=None,
                                       message="bob enrolled on Database practice.")
    Notification.objects.get_or_create(recipient=bob, material=material, defaults={
        "course": course, "message": "New material in Database practice: Week one exercise.",
    })
    print("Demo data ready. New accounts use the password listed in README.md.")


if __name__ == "__main__":
    run()
