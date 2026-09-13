"""Upload handling. Files go to MEDIA_ROOT; only relative paths are stored in SQLite."""
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from PIL import Image

IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
VIDEO_SIGNATURES = {
    ".mp4": lambda head: head[4:8] == b"ftyp",
    ".webm": lambda head: head[:4] == b"\x1a\x45\xdf\xa3",
}


class MediaError(ValueError):
    pass


def _check_size(upload, limit_mb):
    if upload.size > limit_mb * 1024 * 1024:
        raise MediaError(f"{upload.name}: file is larger than {limit_mb} MB.")


def save_image(upload, folder):
    _check_size(upload, settings.MAX_IMAGE_UPLOAD_MB)
    try:
        with Image.open(upload) as img:
            image_format = img.format
            img.verify()
    except Exception:
        raise MediaError(f"{upload.name}: not a valid image.")
    if image_format not in IMAGE_FORMATS:
        raise MediaError(f"{upload.name}: use JPG, PNG, WEBP or GIF.")
    upload.seek(0)
    return default_storage.save(
        f"invitations/{folder}/{uuid.uuid4().hex}{IMAGE_FORMATS[image_format]}", upload
    )


def save_video(upload):
    _check_size(upload, settings.MAX_VIDEO_UPLOAD_MB)
    ext = "." + upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
    check = VIDEO_SIGNATURES.get(ext)
    head = upload.read(12)
    upload.seek(0)
    if not check or not check(head):
        raise MediaError(f"{upload.name}: upload an MP4 or WEBM video.")
    return default_storage.save(f"invitations/videos/{uuid.uuid4().hex}{ext}", upload)


def delete_file(name):
    if name and default_storage.exists(name):
        default_storage.delete(name)


def delete_invitation_files(invitation):
    delete_file(invitation.hero_image.name if invitation.hero_image else "")
    delete_file(invitation.video_file.name if invitation.video_file else "")
    for name in [*(invitation.gallery_images or []), *(invitation.extra_images or {}).values()]:
        delete_file(name)
