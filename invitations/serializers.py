from urllib.parse import quote

from django.conf import settings

from .renderer import share_title_text


def template_to_dict(template):
    return {
        "id": template.id,
        "slug": template.slug,
        "name": template.name,
        "category": template.category,
        "description": template.description,
        "editable_fields": template.editable_fields,
        "groups": template.config_json.get("groups", {}),
        "locked_fields": template.config_json.get("locked_fields", []),
    }


def whatsapp_share_url(title, live_url):
    text = f"{title} 💍 Vanga ellarum! {live_url}"
    return f"https://wa.me/?text={quote(text)}"


def invitation_to_dict(invitation, request, include_template=False):
    def media_url(name):
        return request.build_absolute_uri(settings.MEDIA_URL + name) if name else ""

    title = share_title_text(invitation)
    data = {
        "id": invitation.id,
        "template_id": invitation.template_id,
        "template_name": invitation.template.name,
        "title": title,
        "content_data": invitation.content_data,
        "map_link": invitation.map_link,
        "video_url": invitation.video_url,
        "hero_image": media_url(invitation.hero_image.name if invitation.hero_image else ""),
        "images": {key: media_url(name) for key, name in (invitation.extra_images or {}).items()},
        "gallery_images": [media_url(name) for name in invitation.gallery_images or []],
        "video_file": media_url(invitation.video_file.name if invitation.video_file else ""),
        "live_url": invitation.live_url,
        "is_deployed": invitation.is_deployed,
        "whatsapp_url": whatsapp_share_url(title, invitation.live_url) if invitation.live_url else "",
        "last_deployed_at": invitation.last_deployed_at,
        "created_at": invitation.created_at,
        "updated_at": invitation.updated_at,
    }
    if include_template:
        data["template"] = template_to_dict(invitation.template)
    return data
