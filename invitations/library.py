"""Sync templates_library/<folder>/config.json into the Template table."""
import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def sync_templates():
    from .models import Template

    library = Path(settings.TEMPLATES_LIBRARY_DIR)
    if not library.is_dir():
        return []

    synced = []
    for folder in sorted(p for p in library.iterdir() if (p / "config.json").is_file()):
        try:
            config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Skipping %s: bad config.json (%s)", folder.name, exc)
            continue
        Template.objects.update_or_create(
            slug=folder.name,
            defaults={
                "name": config.get("name", folder.name),
                "category": config.get("category", ""),
                "description": config.get("description", ""),
                "folder_path": f"templates_library/{folder.name}",
                "config_json": config,
                "sort_order": config.get("order", 0),
                "is_active": True,
            },
        )
        synced.append(folder.name)

    Template.objects.exclude(slug__in=synced).update(is_active=False)
    return synced
