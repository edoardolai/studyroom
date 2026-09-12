from django.core.exceptions import ValidationError
from PIL import Image


def validate_photo(photo):
    if photo.size > 2 * 1024 * 1024:
        raise ValidationError("Choose a photo no larger than 2 MB.")
    try:
        with Image.open(photo) as image:
            if image.format not in ("JPEG", "PNG"):
                raise ValidationError("Choose a JPEG or PNG photo.")
            if image.width > 4096 or image.height > 4096:
                raise ValidationError("Photo dimensions must be at most 4096 by 4096 pixels.")
            image.verify()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValidationError("Choose a valid image file.") from error
    finally:
        # Storage needs to read the upload from the beginning after validation.
        photo.seek(0)
