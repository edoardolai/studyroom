from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def validate_material(upload):
    if upload.size > 10 * 1024 * 1024:
        raise ValidationError("Choose a file no larger than 10 MB.")
    extension = Path(upload.name).suffix.lower()
    try:
        if extension == ".pdf":
            reader = PdfReader(upload, strict=True)
            if reader.is_encrypted:
                raise ValidationError("Upload a PDF without password protection.")
            if not len(reader.pages):
                raise ValidationError("The PDF must contain at least one page.")
        elif extension in (".jpg", ".jpeg", ".png"):
            with Image.open(upload) as image:
                expected = "PNG" if extension == ".png" else "JPEG"
                if image.format != expected:
                    raise ValidationError("The image content must match its file extension.")
                if image.width > 4096 or image.height > 4096:
                    raise ValidationError("Images must be at most 4096 by 4096 pixels.")
                image.verify()
        else:
            raise ValidationError("Choose a PDF, JPEG or PNG file.")
    except (OSError, ValueError, PdfReadError, Image.DecompressionBombError) as error:
        raise ValidationError("The file could not be read. Upload a valid PDF or image.") from error
    finally:
        upload.seek(0)
