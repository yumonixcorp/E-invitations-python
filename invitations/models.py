from pathlib import Path

from django.conf import settings
from django.db import models


class Template(models.Model):
    slug = models.SlugField(unique=True)  # same as the folder name
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=300, blank=True)
    thumbnail = models.ImageField(upload_to="thumbnails/", null=True, blank=True)
    folder_path = models.CharField(max_length=200)  # templates_library/template_1
    config_json = models.JSONField()  # editable fields definition
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

    @property
    def editable_fields(self):
        return self.config_json.get("editable_fields", {})

    @property
    def directory(self):
        library = Path(settings.TEMPLATES_LIBRARY_DIR).resolve()
        path = (Path(settings.BASE_DIR) / self.folder_path).resolve()
        if library not in path.parents:
            raise ValueError(f"Template folder outside library: {self.folder_path}")
        return path

    def read_index(self):
        return (self.directory / "index.html").read_text(encoding="utf-8")


class Invitation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invitations")
    template = models.ForeignKey(Template, on_delete=models.PROTECT)

    # Text content, e.g. {"groom_name": "Saran", "bride_name": "Keerthana", ...}
    content_data = models.JSONField(default=dict, blank=True)
    map_link = models.URLField(max_length=2000, blank=True, default="")

    # Media: files live under MEDIA_ROOT, SQLite stores the relative paths.
    hero_image = models.ImageField(upload_to="invitations/hero/", null=True, blank=True)
    gallery_images = models.JSONField(default=list, blank=True)  # ["invitations/gallery/ab12.jpg", ...]
    extra_images = models.JSONField(default=dict, blank=True)  # {"bride_photo": "invitations/images/cd34.jpg"}
    video_file = models.FileField(upload_to="invitations/videos/", null=True, blank=True)
    video_url = models.URLField(blank=True, default="")  # YouTube / Vimeo link

    # Deploy info
    live_url = models.URLField(blank=True, default="")
    netlify_site_id = models.CharField(max_length=200, blank=True)
    is_deployed = models.BooleanField(default=False)
    last_deployed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation #{self.pk} ({self.template})"
