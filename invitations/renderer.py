"""Render a template's index.html with an invitation's content.

Placeholder syntax (a tiny Mustache subset):
  {{key}}                 value, HTML-escaped
  {{#key}}...{{/key}}     shown if key is truthy; repeated for lists ({{.}} = item, {{index}})
  {{^key}}...{{/key}}     shown if key is empty

The whole template is scanned in one pass, so text typed by users (which may
itself contain "{{...}}") is never re-interpreted as a placeholder.
"""
import html
import re
from datetime import date, datetime
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

from .fields import is_content_field, map_urls, video_embed_url

TOKEN_RE = re.compile(
    r"\{\{([#^])\s*([\w.]+)\s*\}\}(.*?)\{\{/\s*\2\s*\}\}|\{\{\s*([\w.]+)\s*\}\}", re.S
)
HEAD_RE = re.compile(r"(<head[^>]*>)", re.I)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def render_string(source, ctx):
    def replace(match):
        kind, key, inner, var = match.groups()
        if var is not None:
            value = ctx.get(var)
            if value is None:
                return ""
            return value if isinstance(value, SafeString) else escape(value)
        value = ctx.get(key)
        if kind == "^":
            return "" if value else render_string(inner, ctx)
        if not value:
            return ""
        if isinstance(value, (list, tuple)):
            return "".join(
                render_string(inner, {**ctx, ".": item, "index": i})
                for i, item in enumerate(value, 1)
            )
        return render_string(inner, ctx)

    return TOKEN_RE.sub(replace, source)


def _date_values(key, raw):
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return {key: raw}
    return {
        key: f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]} {d.year}",
        f"{key}_iso": d.isoformat(),
        f"{key}_day": str(d.day),
        f"{key}_day2": f"{d.day:02d}",
        f"{key}_month": MONTHS[d.month - 1],
        f"{key}_month_short": MONTHS[d.month - 1][:3],
        f"{key}_month_num": f"{d.month:02d}",
        f"{key}_year": str(d.year),
        f"{key}_weekday": WEEKDAYS[d.weekday()],
        f"{key}_short": f"{MONTHS[d.month - 1][:3]} {d.day}, {d.year}",
    }


def _time_values(key, raw):
    try:
        t = datetime.strptime(raw, "%H:%M")
    except ValueError:
        return {key: raw}
    hour = t.hour % 12 or 12
    return {key: f"{hour}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}", f"{key}_24": raw}


def build_context(template, content, *, hero_image="", images=None, gallery=(), video_file="",
                  video_url="", map_link="", og_image=""):
    config = template.config_json
    fields = template.editable_fields
    content = content or {}
    images = images or {}
    ctx = {}
    first_date = first_time = None

    for key, spec in fields.items():
        field_type = spec.get("type")
        raw = str(content.get(key) or "").strip()
        if field_type in ("text", "url"):
            ctx[key] = raw
            if raw:
                ctx[f"{key}_initial"] = raw[0].upper()
        elif field_type == "textarea":
            ctx[key] = mark_safe(escape(raw).replace("\n", "<br>"))
        elif field_type == "location":
            ctx[key] = raw
            if raw:
                ctx[f"{key}_embed"], ctx[f"{key}_directions"] = map_urls("", raw)
        elif field_type == "date" and raw:
            ctx.update(_date_values(key, raw))
            if not spec.get("no_countdown"):
                first_date = first_date or ctx.get(f"{key}_iso")
        elif field_type == "time" and raw:
            ctx.update(_time_values(key, raw))
            if not spec.get("no_countdown"):
                first_time = first_time or ctx.get(f"{key}_24")
        elif field_type == "image" and key != "hero_image":
            ctx[key] = images.get(key, "")

    # A "map" field pinned to a location field ("for": "event_1_location") overrides its map.
    for key, spec in fields.items():
        if spec.get("type") == "map" and key != "map_link":
            url = str(content.get(key) or "").strip()
            ctx[key] = url
            target = spec.get("for")
            if url and target:
                ctx[f"{target}_embed"], ctx[f"{target}_directions"] = map_urls(url, content.get(target, ""))

    if first_date:
        ctx["countdown_target"] = f"{first_date}T{first_time or '00:00'}:00"

    title = html.unescape(render_string(config.get("share_title", template.name), ctx)).strip()
    ctx["share_title"] = title or template.name
    ctx["share_description"] = html.unescape(
        render_string(config.get("share_description", ""), ctx)
    ).strip()

    query = ", ".join(
        str(content.get(k)).strip()
        for k in config.get("map_query_fields", ["venue_name", "venue_address"])
        if content.get(k)
    )
    map_embed, map_directions = map_urls(map_link, query)
    video_embed = video_embed_url(video_url)
    gallery = list(gallery)

    ctx.update({
        "hero_image": hero_image,
        "gallery_images": gallery,
        "gallery_preview": gallery[:3],
        "has_gallery": bool(gallery),
        "video_embed": video_embed,
        "video_file": "" if video_embed else video_file,
        "has_video": bool(video_embed or video_file),
        "map_embed": map_embed,
        "map_directions": map_directions,
        "has_map": bool(map_embed or map_directions),
        "og_image": og_image,
        "year": str(date.today().year),
    })

    # has_<group> is true when any field in that config group has a value,
    # so whole page sections can hide themselves when left empty.
    for key, spec in fields.items():
        group = spec.get("group")
        if not group:
            continue
        field_type = spec.get("type")
        if is_content_field(key, spec):
            value = content.get(key)
        elif field_type == "video":
            value = ctx["has_video"]
        elif field_type == "map":
            value = ctx["has_map"]
        else:
            value = ctx.get(key)
        flag = f"has_{group}"
        ctx[flag] = bool(ctx.get(flag)) or bool(value)
    return ctx


def sample_content(template):
    return {k: v.get("sample", "") for k, v in template.editable_fields.items() if "sample" in v}


def render_template_sample(template, request):
    """Template filled with config "sample" values. Image samples are paths inside the
    template folder (e.g. "sample/bride.jpg"), resolved through the preview <base href>."""
    fields = template.editable_fields
    samples = sample_content(template)
    images = {
        k: v for k, v in samples.items()
        if fields[k].get("type") == "image" and k != "hero_image" and isinstance(v, str)
    }
    hero = samples.get("hero_image") if isinstance(samples.get("hero_image"), str) else ""
    gallery = samples.get("gallery_images") if isinstance(samples.get("gallery_images"), list) else []
    ctx = build_context(
        template, samples, hero_image=hero, images=images, gallery=gallery,
        video_url=samples.get("video_url", "") if isinstance(samples.get("video_url"), str) else "",
    )
    return _with_base(render_string(template.read_index(), ctx), template, request)


def render_invitation(invitation, *, mode="preview", request=None, overrides=None, site_url=""):
    """Returns (html, assets). assets is a list of (absolute_source_path, relative_dest)
    that must be copied next to index.html when deploying."""
    overrides = overrides or {}
    template = invitation.template
    assets = []

    def media(name, dest_stem):
        if not name:
            return ""
        if mode == "preview":
            return request.build_absolute_uri(settings.MEDIA_URL + name)
        dest = f"assets/{dest_stem}{PurePosixPath(name).suffix}"
        assets.append((default_storage.path(name), dest))
        return dest

    hero = media(invitation.hero_image.name if invitation.hero_image else "", "hero")
    images = {
        key: media(name, key.replace("_", "-"))
        for key, name in (invitation.extra_images or {}).items()
        if template.editable_fields.get(key, {}).get("type") == "image"
    }
    gallery = [media(name, f"gallery-{i}") for i, name in enumerate(invitation.gallery_images or [], 1)]
    video = media(invitation.video_file.name if invitation.video_file else "", "video")
    og_image = ""
    if hero:
        og_image = hero if mode == "preview" else f"{site_url.rstrip('/')}/{hero}" if site_url else ""

    ctx = build_context(
        template,
        overrides.get("content_data", invitation.content_data),
        hero_image=hero,
        images=images,
        gallery=gallery,
        video_file=video,
        video_url=overrides.get("video_url", invitation.video_url),
        map_link=overrides.get("map_link", invitation.map_link),
        og_image=og_image,
    )
    output = render_string(template.read_index(), ctx)
    if mode == "preview":
        output = _with_base(output, template, request)
    return output, assets


def share_title_text(invitation):
    return build_context(invitation.template, invitation.content_data)["share_title"]


def _with_base(output, template, request):
    """Point relative style.css/script.js at /library/<folder>/ for iframe previews."""
    base = request.build_absolute_uri(f"/library/{template.directory.name}/")
    tag = f'<base href="{escape(base)}">'
    return HEAD_RE.sub(lambda m: m.group(1) + tag, output, count=1)
