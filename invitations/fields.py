"""Validation for the user-editable fields declared in each template's config.json.

Only fields listed under "editable_fields" can be changed; colors, fonts,
animations and layout live in the template's CSS/JS and are never exposed.

Field types:
  text, textarea, date, time, location, url -> stored in Invitation.content_data
  map (any key except "map_link")        -> Google Maps URL in content_data
  map (key "map_link")                   -> Invitation.map_link
  image (key "hero_image")               -> Invitation.hero_image
  image (any other key)                  -> Invitation.extra_images[key]
  image_multiple (key "gallery_images")  -> Invitation.gallery_images
  video (key "video_url")                -> Invitation.video_url / video_file
"""
import re
from datetime import date, datetime
from urllib.parse import quote, urlparse

TEXT_TYPES = {"text", "textarea", "date", "time", "location", "url"}
DEFAULT_MAX_LENGTH = {"text": 120, "textarea": 1500, "date": 10, "time": 5, "location": 250, "url": 300}
URL_RE = re.compile(r"^https?://[^\s<>\"'`]+$", re.I)

YOUTUBE_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([\w-]{11})"
)
VIMEO_RE = re.compile(r"vimeo\.com/(?:video/)?(\d+)")
GOOGLE_HOST_RE = re.compile(r"^(?:www\.|maps\.)?google\.(?:com|co\.[a-z]{2}|[a-z]{2})$")
SHORT_MAP_HOSTS = {"goo.gl", "maps.app.goo.gl"}
IFRAME_SRC_RE = re.compile(r"""<iframe[^>]*\ssrc=["']([^"']+)["']""", re.I)


class FieldValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def is_content_field(key, spec):
    """True for fields whose values live in Invitation.content_data."""
    field_type = spec.get("type")
    return field_type in TEXT_TYPES or (field_type == "map" and key != "map_link")


def image_keys(template):
    return [k for k, s in template.editable_fields.items() if s.get("type") == "image"]


def clean_content_data(template, data, lenient=False):
    """Validate content_data. With lenient=True invalid values are dropped instead of raising
    (used by the live preview while the user is still typing)."""
    if not isinstance(data, dict):
        if lenient:
            return {}
        raise FieldValidationError({"content_data": "Must be an object."})
    errors, cleaned = {}, {}
    for key, spec in template.editable_fields.items():
        if not is_content_field(key, spec) or key not in data:
            continue
        field_type = spec.get("type")
        value = "" if data[key] is None else str(data[key]).strip()
        error = None
        if field_type == "map":
            try:
                value = clean_map_link(value)
            except FieldValidationError as exc:
                error = exc.errors["map_link"]
        else:
            max_length = spec.get("max_length", DEFAULT_MAX_LENGTH[field_type])
            if len(value) > max_length:
                error = f"Maximum {max_length} characters."
            elif value and field_type == "date":
                try:
                    date.fromisoformat(value)
                except ValueError:
                    error = "Use YYYY-MM-DD."
            elif value and field_type == "time":
                try:
                    datetime.strptime(value, "%H:%M")
                except ValueError:
                    error = "Use HH:MM (24-hour)."
            elif value and field_type == "url" and not URL_RE.match(value):
                error = "Use a full link starting with https://"
        if error:
            if not lenient:
                errors[key] = error
            continue
        cleaned[key] = value
    if errors:
        raise FieldValidationError(errors)
    return cleaned


def clean_video_url(raw):
    """Accept YouTube/Vimeo links only. Returns the cleaned URL ('' if empty)."""
    raw = (raw or "").strip()
    if raw and not video_embed_url(raw):
        raise FieldValidationError({"video_url": "Paste a YouTube or Vimeo link."})
    return raw


def video_embed_url(url):
    if not url:
        return ""
    match = YOUTUBE_RE.search(url)
    if match:
        return f"https://www.youtube-nocookie.com/embed/{match.group(1)}"
    match = VIMEO_RE.search(url)
    if match:
        return f"https://player.vimeo.com/video/{match.group(1)}"
    return ""


def clean_map_link(raw):
    """Accept a Google Maps link, embed URL or the full <iframe> embed code."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    iframe = IFRAME_SRC_RE.search(raw)
    if iframe:
        raw = iframe.group(1).replace("&amp;", "&")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (GOOGLE_HOST_RE.match(host) or host in SHORT_MAP_HOSTS):
        raise FieldValidationError({"map_link": "Paste a Google Maps link (https://maps.app.goo.gl/... or embed code)."})
    if len(raw) > 2000:
        raise FieldValidationError({"map_link": "Link is too long."})
    return raw


def is_map_embed(url):
    parsed = urlparse(url or "")
    return bool(GOOGLE_HOST_RE.match((parsed.hostname or "").lower())) and (
        parsed.path.startswith("/maps/embed") or "output=embed" in parsed.query
    )


def map_urls(map_link, query):
    """Return (embed_src, directions_href) for a venue."""
    query = (query or "").strip()
    embed = map_link if is_map_embed(map_link) else ""
    if not embed and query:
        embed = f"https://maps.google.com/maps?q={quote(query)}&output=embed"
    if map_link and not is_map_embed(map_link):
        directions = map_link
    elif query:
        directions = f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
    else:
        directions = ""
    return embed, directions


def missing_required_fields(invitation):
    """Labels of required fields that are still empty (checked before deploy)."""
    missing = []
    content = invitation.content_data or {}
    for key, spec in invitation.template.editable_fields.items():
        if not spec.get("required"):
            continue
        field_type = spec.get("type")
        if is_content_field(key, spec):
            filled = bool(content.get(key))
        elif field_type == "image":
            filled = bool(invitation.hero_image) if key == "hero_image" else bool((invitation.extra_images or {}).get(key))
        elif field_type == "image_multiple":
            filled = bool(invitation.gallery_images)
        elif field_type == "video":
            filled = bool(invitation.video_url or invitation.video_file)
        elif field_type == "map":
            filled = bool(invitation.map_link)
        else:
            filled = True
        if not filled:
            missing.append(spec.get("label", key))
    return missing
