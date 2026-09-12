from functools import partial

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import User


def delete_unused_photo(name, storage, using):
    # A file may still be referenced by another account.
    if name and not User.objects.using(using).filter(photo=name).exists():
        storage.delete(name)


@receiver(pre_save, sender=User)
def remember_previous_photo(sender, instance, raw, using, update_fields, **kwargs):
    instance._previous_photo = ""
    if raw or (update_fields is not None and "photo" not in update_fields):
        return
    if instance.pk:
        instance._previous_photo = (
            User.objects.using(using).filter(pk=instance.pk).values_list("photo", flat=True).first()
        )


@receiver(post_save, sender=User)
def remove_replaced_photo(sender, instance, raw, using, **kwargs):
    if raw:
        return
    previous = getattr(instance, "_previous_photo", "")
    if previous and previous != instance.photo.name:
        # Wait for commit so a rolled-back edit keeps its original photo.
        transaction.on_commit(
            partial(delete_unused_photo, previous, instance.photo.storage, using),
            using=using, robust=True,
        )


@receiver(post_delete, sender=User)
def remove_deleted_users_photo(sender, instance, using, **kwargs):
    if instance.photo:
        transaction.on_commit(
            partial(delete_unused_photo, instance.photo.name, instance.photo.storage, using),
            using=using, robust=True,
        )
