import io
import shutil
import tempfile
import zipfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User

from .fields import FieldValidationError, clean_map_link, map_urls, video_embed_url
from .library import sync_templates
from .models import Invitation, Template

TEMP_MEDIA = tempfile.mkdtemp(prefix="einvite_test_media_")
TEMPLATE_SLUGS = ["home", "home2", "home3", "home4"]


def png_upload(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


class FieldParsingTests(TestCase):
    def test_video_urls(self):
        self.assertEqual(video_embed_url("https://youtu.be/dQw4w9WgXcQ"), "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertEqual(video_embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3"), "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertEqual(video_embed_url("https://vimeo.com/12345"), "https://player.vimeo.com/video/12345")
        self.assertEqual(video_embed_url("https://evil.example/video"), "")

    def test_map_links(self):
        iframe = '<iframe src="https://www.google.com/maps/embed?pb=abc&amp;x=1" width="600"></iframe>'
        self.assertEqual(clean_map_link(iframe), "https://www.google.com/maps/embed?pb=abc&x=1")
        self.assertEqual(clean_map_link("https://maps.app.goo.gl/xyz"), "https://maps.app.goo.gl/xyz")
        with self.assertRaises(FieldValidationError):
            clean_map_link("javascript:alert(1)")
        with self.assertRaises(FieldValidationError):
            clean_map_link("https://google.com.evil.net/maps")
        embed, directions = map_urls("https://maps.app.goo.gl/xyz", "Kalyana Mahal, Madurai")
        self.assertIn("output=embed", embed)
        self.assertEqual(directions, "https://maps.app.goo.gl/xyz")


@override_settings(MEDIA_ROOT=TEMP_MEDIA, NETLIFY_TOKEN="")
class InvitationApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        sync_templates()
        self.template = Template.objects.get(slug="home")
        self.user = User.objects.create(username="s@example.com", email="s@example.com", is_email_verified=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create(self, **content):
        resp = self.client.post("/api/invitations/", {"template_id": self.template.id, "content_data": content}, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        return Invitation.objects.get(pk=resp.data["invitation_id"])

    def preview(self, invitation, **payload):
        resp = self.client.post(f"/api/invitations/{invitation.id}/preview/", payload, format="json")
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_all_templates_render_samples(self):
        self.assertEqual(sorted(Template.objects.filter(is_active=True).values_list("slug", flat=True)), TEMPLATE_SLUGS)
        client = APIClient()
        for template in Template.objects.filter(is_active=True):
            resp = client.get(f"/api/templates/{template.id}/sample/")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode()
            self.assertNotIn("{{", html, template.slug)
            self.assertIn("../_common/css/base.css", html)
            self.assertIn('data-countdown="', html)
        self.assertEqual(client.get("/library/_common/css/sections.css").status_code, 200)
        self.assertEqual(client.get("/library/home/config.json").status_code, 404)

    def test_free_quota_blocks_second_invitation(self):
        self.create()
        resp = self.client.post("/api/invitations/", {"template_id": self.template.id}, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data["code"], "quota_exceeded")

    def test_patch_validates_fields(self):
        inv = self.create()
        resp = self.client.patch(f"/api/invitations/{inv.id}/", {"content_data": {
            "wedding_date": "14/12/2026", "bride_instagram": "javascript:alert(1)", "event_1_map": "https://evil.example/map",
        }}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.data["fields"]), {"wedding_date", "bride_instagram", "event_1_map"})
        resp = self.client.patch(f"/api/invitations/{inv.id}/", {
            "content_data": {"groom_name": "Saran", "wedding_date": "2026-12-14", "not_editable": "x",
                             "bride_instagram": "https://instagram.com/keerthana"},
            "video_url": "https://youtu.be/dQw4w9WgXcQ",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        inv.refresh_from_db()
        self.assertNotIn("not_editable", inv.content_data)

    def test_preview_escapes_user_content(self):
        inv = self.create(groom_name="<script>alert(1)</script>", bride_name="{{bride_bio}}", bride_bio="Hello")
        html = self.preview(inv)
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("{{bride_bio}}", html)  # user braces are not re-interpreted
        self.assertIn('<base href="http://testserver/library/home/">', html)

    def test_empty_sections_are_hidden(self):
        inv = self.create(bride_name="Keerthana", groom_name="Saran", wedding_date="2026-12-14")
        html = self.preview(inv)
        for anchor in ('id="story"', 'id="people"', 'id="rsvp"', 'id="events"', 'href="#story"'):
            self.assertNotIn(anchor, html)
        html = self.preview(inv, content_data={
            "story_1_title": "How We Met", "event_1_title": "Reception", "event_1_location": "Anna Nagar, Madurai",
            "rsvp_whatsapp": "9876543210",
        })
        self.assertIn('id="story"', html)
        self.assertIn('href="#story"', html)
        self.assertIn('data-whatsapp="9876543210"', html)
        self.assertIn("data-map-embed=\"https://maps.google.com/maps?q=Anna%20Nagar%2C%20Madurai&amp;output=embed\"", html)

    def test_preview_uses_unsaved_overrides(self):
        inv = self.create(groom_name="Saran")
        html = self.preview(inv, content_data={"groom_name": "Arjun", "wedding_date": "bad-date"})
        self.assertIn("Arjun", html)  # invalid values are skipped, valid ones still preview
        inv.refresh_from_db()
        self.assertEqual(inv.content_data["groom_name"], "Saran")

    def test_media_upload_and_delete(self):
        inv = self.create()
        resp = self.client.post(f"/api/invitations/{inv.id}/media/", {
            "hero_image": png_upload(), "couple_photo": png_upload("c.png"),
            "gallery_images": [png_upload("a.png"), png_upload("b.png")],
        }, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data["gallery_images"]), 2)
        self.assertIn("/media/invitations/images/", resp.data["images"]["couple_photo"])
        self.assertIn("/media/invitations/images/", self.preview(inv))

        resp = self.client.delete(f"/api/invitations/{inv.id}/media/gallery/0/")
        self.assertEqual(len(resp.data["gallery_images"]), 1)
        resp = self.client.delete(f"/api/invitations/{inv.id}/media/couple_photo/")
        self.assertNotIn("couple_photo", resp.data["images"])
        self.assertEqual(self.client.delete(f"/api/invitations/{inv.id}/media/not_a_field/").status_code, 400)

    def test_invalid_image_rejected(self):
        inv = self.create()
        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        resp = self.client.post(f"/api/invitations/{inv.id}/media/", {"hero_image": fake}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.client.post(f"/api/invitations/{inv.id}/media/", {}, format="multipart").status_code, 400)

    def test_other_users_cannot_access(self):
        inv = self.create()
        other = User.objects.create(username="o@example.com", email="o@example.com")
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/invitations/{inv.id}/").status_code, 404)
        self.assertEqual(client.post(f"/api/invitations/{inv.id}/deploy/").status_code, 404)

    def test_deploy_requires_fields(self):
        inv = self.create(groom_name="Saran")
        resp = self.client.post(f"/api/invitations/{inv.id}/deploy/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Bride name", resp.data["missing"])

    @override_settings(NETLIFY_TOKEN="test-token")
    def test_deploy_to_netlify(self):
        inv = self.create(bride_name="Keerthana", groom_name="Saran", wedding_date="2026-12-14")
        self.client.post(f"/api/invitations/{inv.id}/media/", {"hero_image": png_upload(), "couple_photo": png_upload()}, format="multipart")
        uploaded = {}

        def fake_request(method, url, headers=None, timeout=None, **kwargs):
            self.assertEqual(headers["Authorization"], "Bearer test-token")
            if method == "POST" and url.endswith("/sites"):
                return FakeResponse(201, {"id": "site1", "site_id": "site1", "ssl_url": "https://saran-weds.netlify.app"})
            if method == "POST" and url.endswith("/sites/site1/deploys"):
                uploaded["zip"] = kwargs["data"].read()
                return FakeResponse(200, {"id": "dep1", "state": "uploaded"})
            if method == "GET" and url.endswith("/deploys/dep1"):
                return FakeResponse(200, {"state": "ready"})
            raise AssertionError(f"Unexpected call {method} {url}")

        with mock.patch("invitations.netlify.requests.request", side_effect=fake_request):
            resp = self.client.post(f"/api/invitations/{inv.id}/deploy/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["live_url"], "https://saran-weds.netlify.app")
        self.assertIn("wa.me", resp.data["whatsapp_url"])

        archive = zipfile.ZipFile(io.BytesIO(uploaded["zip"]))
        names = archive.namelist()
        for expected in ("index.html", "style.css", "assets/hero.png", "assets/couple-photo.png",
                         "_common/css/base.css", "_common/css/sections.css", "_common/js/common.js",
                         "_common/img/floral-peony.svg"):
            self.assertIn(expected, names)
        self.assertNotIn("config.json", names)
        html = archive.read("index.html").decode()
        self.assertIn("Keerthana", html)
        self.assertIn('src="assets/hero.png"', html)
        self.assertIn('src="assets/couple-photo.png"', html)
        self.assertIn("https://saran-weds.netlify.app/assets/hero.png", html)  # og:image
        self.assertNotIn("<base", html)

        inv.refresh_from_db()
        self.assertTrue(inv.is_deployed)
        self.assertEqual(inv.netlify_site_id, "site1")
