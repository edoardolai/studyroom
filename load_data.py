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


def rename_demo_user(old_username, username, first_name, last_name):
    old_user = User.objects.filter(username=old_username).first()
    if old_user and not User.objects.filter(username=username).exists():
        old_user.username = username
        old_user.first_name = first_name
        old_user.last_name = last_name
        old_user.email = f"{username}@example.com"
        old_user.save(update_fields=["username", "first_name", "last_name", "email"])


def demo_admin():
    admin, created = User.objects.get_or_create(username="admin", defaults={
        "first_name": "Site", "last_name": "Admin", "role": "teacher",
        "email": "admin@example.com", "password": make_password(DEMO_PASSWORD),
        "is_staff": True, "is_superuser": True,
    })
    if not admin.is_staff or not admin.is_superuser:
        raise ValueError("admin exists without administrator permissions; check the demo account.")
    print(f"{'Created' if created else 'Kept'} account: admin")


def run():
    rename_demo_user("bob", "harry", "Harry", "Potter")
    rename_demo_user("alice", "draco", "Draco", "Malfoy")
    rename_demo_user("john", "ron", "Ron", "Weasley")
    rename_demo_user("grant", "snape", "Severus", "Snape")
    rename_demo_user("mark", "mcgonagall", "Minerva", "McGonagall")

    harry = demo_user("harry", "Harry", "Potter", "student")
    ron = demo_user("ron", "Ron", "Weasley", "student")
    hermione = demo_user("hermione", "Hermione", "Granger", "student")
    draco = demo_user("draco", "Draco", "Malfoy", "student")
    snape = demo_user("snape", "Severus", "Snape", "teacher")
    mcgonagall = demo_user("mcgonagall", "Minerva", "McGonagall", "teacher")
    demo_admin()

    course = Course.objects.filter(teacher=snape, title="Database practice").first()
    if course:
        course.title = "Potions"
        course.description = "Study potion ingredients, preparation order and safe handling."
        course.save(update_fields=["title", "description"])
    else:
        course, _ = Course.objects.get_or_create(teacher=snape, title="Potions", defaults={
            "description": "Study potion ingredients, preparation order and safe handling.",
        })

    other_course = Course.objects.filter(teacher=mcgonagall, title="Web application design").first()
    if other_course:
        other_course.title = "Transfiguration"
        other_course.description = "Practise transformation theory and controlled spell work."
        other_course.save(update_fields=["title", "description"])
    else:
        other_course, _ = Course.objects.get_or_create(
            teacher=mcgonagall, title="Transfiguration",
            defaults={"description": "Practise transformation theory and controlled spell work."},
        )

    Enrolment.objects.get_or_create(course=course, student=harry)
    Enrolment.objects.get_or_create(course=other_course, student=harry)
    Enrolment.objects.get_or_create(course=course, student=ron)
    Enrolment.objects.get_or_create(course=course, student=hermione)
    Enrolment.objects.get_or_create(course=other_course, student=draco, defaults={"is_blocked": True})

    StatusUpdate.objects.filter(
        author=harry, body="Working through the joins exercise this week.",
    ).update(body="Revising the potion ingredients before class.")
    StatusUpdate.objects.filter(
        author=draco, body="Reading about Django forms and validation.",
    ).update(body="Practising the match-to-needle transformation.")
    StatusUpdate.objects.get_or_create(author=harry, body="Revising the potion ingredients before class.")
    StatusUpdate.objects.get_or_create(author=draco, body="Practising the match-to-needle transformation.")
    Feedback.objects.filter(
        course=course, student=harry,
        body="The exercise helped me understand the join. A three-table example would be useful next.",
    ).update(body="The ingredient guide was useful. Another example potion would help for revision.")
    Feedback.objects.get_or_create(course=course, student=harry, defaults={
        "body": "The ingredient guide was useful. Another example potion would help for revision.",
    })
    ChatMessage.objects.filter(
        course=course, author=harry, body="Should we join on the student ID?",
    ).update(body="Do the crushed ingredients go in first?")
    ChatMessage.objects.filter(
        course=course, author=snape, body="Yes. Match the student ID before selecting the columns.",
    ).update(body="Yes, before you begin heating the cauldron.")
    ChatMessage.objects.get_or_create(course=course, author=harry, body="Do the crushed ingredients go in first?")
    ChatMessage.objects.get_or_create(course=course, author=snape, body="Yes, before you begin heating the cauldron.")

    material = CourseMaterial.objects.filter(course=course, title="Week one exercise").first()
    if material:
        old_file = material.file.name
        material.title = "Potion ingredients"
        path = Path(__file__).resolve().parent / "demo_materials" / "potion_ingredients.pdf"
        with path.open("rb") as source:
            material.file.save("potion_ingredients.pdf", File(source), save=False)
        material.save(update_fields=["title", "file"])
        if old_file != material.file.name:
            material.file.storage.delete(old_file)
    else:
        material = CourseMaterial.objects.filter(course=course, title="Potion ingredients").first()
        if material is None:
            material = CourseMaterial(course=course, title="Potion ingredients")
            path = Path(__file__).resolve().parent / "demo_materials" / "potion_ingredients.pdf"
            with path.open("rb") as source:
                material.file.save("potion_ingredients.pdf", File(source))

    transfiguration_material = CourseMaterial.objects.filter(
        course=other_course, title="Transfiguration notes",
    ).first()
    if transfiguration_material is None:
        transfiguration_material = CourseMaterial(course=other_course, title="Transfiguration notes")
        path = Path(__file__).resolve().parent / "demo_materials" / "transfiguration_notes.pdf"
        with path.open("rb") as source:
            transfiguration_material.file.save("transfiguration_notes.pdf", File(source))

    # Seed example notices directly: setup should not need a running worker.
    Notification.objects.filter(
        recipient=snape, course=course, message="bob enrolled on Database practice.",
    ).update(message="harry enrolled on Potions.")
    Notification.objects.get_or_create(recipient=snape, course=course, material=None,
                                       message="harry enrolled on Potions.")
    Notification.objects.filter(
        recipient=harry, material=material,
        message="New material in Database practice: Week one exercise.",
    ).update(message="New material in Potions: Potion ingredients.")
    Notification.objects.get_or_create(recipient=harry, material=material, defaults={
        "course": course, "message": "New material in Potions: Potion ingredients.",
    })
    print("Demo data ready. New accounts use the password listed in README.md.")


if __name__ == "__main__":
    run()
