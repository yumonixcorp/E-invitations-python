"""Deploy a rendered invitation to Netlify as a static site."""
import logging
import secrets
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from .renderer import render_invitation, share_title_text

logger = logging.getLogger(__name__)

EXCLUDED_TEMPLATE_FILES = ("config.json", "thumbnail.*", "sample")
COMMON_DIR_NAME = "_common"  # shared CSS/JS referenced by templates as ../_common/


class DeployError(Exception):
    pass


def _api(method, path, *, headers=None, timeout=60, **kwargs):
    all_headers = {"Authorization": f"Bearer {settings.NETLIFY_TOKEN}", **(headers or {})}
    try:
        return requests.request(
            method, f"{settings.NETLIFY_API_BASE}{path}", headers=all_headers, timeout=timeout, **kwargs
        )
    except requests.RequestException as exc:
        raise DeployError(f"Could not reach Netlify: {exc}") from exc


def _error_detail(resp):
    try:
        return resp.json().get("message") or resp.text[:200]
    except ValueError:
        return resp.text[:200]


def _site_name(invitation):
    base = slugify(share_title_text(invitation))[:40].strip("-") or "invitation"
    return f"{base}-{secrets.token_hex(3)}"


def _ensure_site(invitation):
    """Reuse the invitation's existing Netlify site, or create a new one."""
    if invitation.netlify_site_id:
        resp = _api("GET", f"/sites/{invitation.netlify_site_id}")
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code != 404:
            raise DeployError(f"Netlify error ({resp.status_code}): {_error_detail(resp)}")

    for _ in range(3):
        resp = _api("POST", "/sites", json={"name": _site_name(invitation)})
        if resp.status_code in (200, 201):
            return resp.json()
        if resp.status_code != 422:  # 422 = subdomain already taken, retry with a new suffix
            break
    raise DeployError(f"Could not create Netlify site ({resp.status_code}): {_error_detail(resp)}")


def build_site_folder(invitation, dest, site_url=""):
    """Template files + rendered index.html + user media, ready to upload."""
    shutil.copytree(
        invitation.template.directory, dest, ignore=shutil.ignore_patterns(*EXCLUDED_TEMPLATE_FILES)
    )
    html, assets = render_invitation(invitation, mode="deploy", site_url=site_url)
    (dest / "index.html").write_text(html, encoding="utf-8")
    # "../_common/x.css" from the site root resolves to "/_common/x.css" on Netlify.
    common = invitation.template.directory.parent / COMMON_DIR_NAME
    if f"{COMMON_DIR_NAME}/" in html and common.is_dir():
        shutil.copytree(common, dest / COMMON_DIR_NAME)
    for source, relative in assets:
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return dest


def _zip_folder(folder, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in folder.rglob("*"):
            if path.is_file():
                zipf.write(path, path.relative_to(folder).as_posix())


def _wait_until_ready(deploy_id, attempts=20, delay=1.5):
    for _ in range(attempts):
        resp = _api("GET", f"/deploys/{deploy_id}")
        if resp.status_code == 200:
            state = resp.json().get("state")
            if state == "ready":
                return
            if state == "error":
                raise DeployError(resp.json().get("error_message") or "Netlify deploy failed.")
        time.sleep(delay)
    logger.warning("Deploy %s still processing; returning URL anyway", deploy_id)


def deploy_to_netlify(invitation):
    if not settings.NETLIFY_TOKEN:
        raise DeployError("Netlify is not configured. Set NETLIFY_TOKEN in .env.")

    site = _ensure_site(invitation)
    site_id = site.get("site_id") or site["id"]
    site_url = site.get("ssl_url") or site.get("url") or ""

    with tempfile.TemporaryDirectory(prefix=f"invitation_{invitation.pk}_") as tmp:
        folder = build_site_folder(invitation, Path(tmp) / "site", site_url)
        zip_path = Path(tmp) / "site.zip"
        _zip_folder(folder, zip_path)
        with open(zip_path, "rb") as fh:
            resp = _api(
                "POST",
                f"/sites/{site_id}/deploys",
                headers={"Content-Type": "application/zip"},
                data=fh,
                timeout=300,
            )
    if resp.status_code not in (200, 201):
        raise DeployError(f"Netlify deploy failed ({resp.status_code}): {_error_detail(resp)}")

    deploy = resp.json()
    _wait_until_ready(deploy["id"])

    invitation.live_url = site_url or deploy.get("ssl_url") or deploy.get("url", "")
    invitation.netlify_site_id = site_id
    invitation.is_deployed = True
    invitation.last_deployed_at = timezone.now()
    invitation.save(update_fields=["live_url", "netlify_site_id", "is_deployed", "last_deployed_at"])
    return invitation.live_url


def delete_netlify_site(site_id):
    """Best effort: take the live site down when an invitation is deleted."""
    if not (site_id and settings.NETLIFY_TOKEN):
        return
    try:
        _api("DELETE", f"/sites/{site_id}")
    except DeployError:
        logger.warning("Could not delete Netlify site %s", site_id)
