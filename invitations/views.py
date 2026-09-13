from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.quota import quota_summary, reserve_invitation_slot

from .fields import (
    FieldValidationError,
    clean_content_data,
    clean_map_link,
    clean_video_url,
    image_keys,
    missing_required_fields,
)
from .media import MediaError, delete_file, delete_invitation_files, save_image, save_video
from .models import Invitation, Template
from .netlify import DeployError, delete_netlify_site, deploy_to_netlify
from .renderer import render_invitation, render_template_sample
from .serializers import invitation_to_dict, template_to_dict, whatsapp_share_url


def _get_invitation(request, pk):
    return get_object_or_404(Invitation.objects.select_related("template"), pk=pk, user=request.user)


def _field_types(template):
    return {spec.get("type"): spec for spec in template.editable_fields.values()}


def _html(content):
    response = HttpResponse(content, content_type="text/html; charset=utf-8")
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def _validation_error(errors):
    return Response({"error": "Please fix the highlighted fields.", "fields": errors}, status=400)


class TemplateListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response([template_to_dict(t) for t in Template.objects.filter(is_active=True)])


class TemplateSampleView(APIView):
    """Public preview of a template filled with its sample values (gallery thumbnails)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        template = get_object_or_404(Template, pk=pk, is_active=True)
        return _html(render_template_sample(template, request))


class InvitationListCreateView(APIView):
    def get(self, request):
        invitations = Invitation.objects.filter(user=request.user).select_related("template")
        return Response({
            "invitations": [invitation_to_dict(inv, request) for inv in invitations],
            "quota": quota_summary(request.user),
        })

    def post(self, request):
        try:
            template = Template.objects.get(pk=int(request.data.get("template_id")), is_active=True)
        except (TypeError, ValueError, Template.DoesNotExist):
            return Response({"error": "Choose a valid template."}, status=400)
        try:
            content = clean_content_data(template, request.data.get("content_data") or {})
        except FieldValidationError as exc:
            return _validation_error(exc.errors)

        with transaction.atomic():
            if not reserve_invitation_slot(request.user):
                return Response(
                    {"error": "Free quota finished. Please subscribe.", "code": "quota_exceeded"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            invitation = Invitation.objects.create(
                user=request.user, template=template, content_data=content
            )
        return Response(
            {"invitation_id": invitation.id, "invitation": invitation_to_dict(invitation, request)},
            status=201,
        )


class InvitationDetailView(APIView):
    def get(self, request, pk):
        invitation = _get_invitation(request, pk)
        return Response(invitation_to_dict(invitation, request, include_template=True))

    def patch(self, request, pk):
        invitation = _get_invitation(request, pk)
        errors = {}
        cleaners = {
            "content_data": lambda v: {**invitation.content_data, **clean_content_data(invitation.template, v)},
            "map_link": clean_map_link,
            "video_url": clean_video_url,
        }
        for field, clean in cleaners.items():
            if field not in request.data:
                continue
            try:
                setattr(invitation, field, clean(request.data[field]))
            except FieldValidationError as exc:
                errors.update(exc.errors)
        if errors:
            return _validation_error(errors)
        if invitation.video_url and invitation.video_file:
            delete_file(invitation.video_file.name)
            invitation.video_file = None
        invitation.save()
        return Response(invitation_to_dict(invitation, request, include_template=True))

    def delete(self, request, pk):
        invitation = _get_invitation(request, pk)
        delete_netlify_site(invitation.netlify_site_id)
        delete_invitation_files(invitation)
        invitation.delete()
        return Response(status=204)


class InvitationMediaView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        invitation = _get_invitation(request, pk)
        types = _field_types(invitation.template)
        files = request.FILES
        saved, replaced = [], []
        extra_images = dict(invitation.extra_images or {})
        try:
            if not any(key in files for key in [*image_keys(invitation.template), "gallery_images", "video_file"]):
                raise MediaError("Nothing to upload for this template.")

            for key in image_keys(invitation.template):
                if key not in files:
                    continue
                saved.append(save_image(files[key], "hero" if key == "hero_image" else "images"))
                if key == "hero_image":
                    if invitation.hero_image:
                        replaced.append(invitation.hero_image.name)
                    invitation.hero_image.name = saved[-1]
                else:
                    if extra_images.get(key):
                        replaced.append(extra_images[key])
                    extra_images[key] = saved[-1]
            invitation.extra_images = extra_images

            gallery_files = files.getlist("gallery_images")
            if gallery_files:
                spec = types.get("image_multiple")
                if not spec:
                    raise MediaError("This template has no photo gallery.")
                limit = spec.get("max", 6)
                if len(invitation.gallery_images) + len(gallery_files) > limit:
                    raise MediaError(f"Gallery allows up to {limit} photos.")
                for upload in gallery_files:
                    saved.append(save_image(upload, "gallery"))
                    invitation.gallery_images = [*invitation.gallery_images, saved[-1]]

            if "video_file" in files:
                if "video" not in types:
                    raise MediaError("This template has no video section.")
                saved.append(save_video(files["video_file"]))
                if invitation.video_file:
                    replaced.append(invitation.video_file.name)
                invitation.video_file.name = saved[-1]
                invitation.video_url = ""
        except MediaError as exc:
            # Nothing was written to the DB; discard the files saved in this request.
            for name in saved:
                delete_file(name)
            return Response({"error": str(exc)}, status=400)

        invitation.save()
        for name in replaced:
            delete_file(name)
        return Response(invitation_to_dict(invitation, request, include_template=True))


class InvitationMediaDeleteView(APIView):
    def delete(self, request, pk, field, index=None):
        invitation = _get_invitation(request, pk)
        if field == "gallery":
            if index is None or not 0 <= index < len(invitation.gallery_images):
                return Response({"error": "No such photo."}, status=404)
            delete_file(invitation.gallery_images[index])
            invitation.gallery_images = [
                name for i, name in enumerate(invitation.gallery_images) if i != index
            ]
        elif field in ("hero_image", "video_file"):
            file_field = getattr(invitation, field)
            delete_file(file_field.name if file_field else "")
            setattr(invitation, field, None)
        elif field in image_keys(invitation.template):
            extra_images = dict(invitation.extra_images or {})
            delete_file(extra_images.pop(field, ""))
            invitation.extra_images = extra_images
        else:
            return Response({"error": "Unknown media field."}, status=400)
        invitation.save()
        return Response(invitation_to_dict(invitation, request, include_template=True))


class InvitationPreviewView(APIView):
    """Render HTML for the editor iframe. Unsaved form values can be sent as overrides."""
    parser_classes = [JSONParser]

    def post(self, request, pk):
        invitation = _get_invitation(request, pk)
        overrides = {}
        cleaners = {
            "content_data": lambda v: {
                **invitation.content_data, **clean_content_data(invitation.template, v, lenient=True)
            },
            "map_link": clean_map_link,
            "video_url": clean_video_url,
        }
        for field, clean in cleaners.items():
            if field in request.data:
                try:
                    overrides[field] = clean(request.data[field])
                except FieldValidationError:
                    pass  # keep the saved value while the user is still typing
        html, _ = render_invitation(invitation, mode="preview", request=request, overrides=overrides)
        return _html(html)


class DeployInvitationView(APIView):
    def post(self, request, pk):
        invitation = _get_invitation(request, pk)
        missing = missing_required_fields(invitation)
        if missing:
            return Response(
                {"error": f"Please fill: {', '.join(missing)}", "missing": missing}, status=400
            )
        if not settings.NETLIFY_TOKEN:
            return Response(
                {"error": "Netlify is not configured. Set NETLIFY_TOKEN in .env."}, status=503
            )
        try:
            live_url = deploy_to_netlify(invitation)
        except DeployError as exc:
            return Response({"error": str(exc)}, status=502)
        data = invitation_to_dict(invitation, request, include_template=True)
        return Response({
            "live_url": live_url,
            "whatsapp_url": whatsapp_share_url(data["title"], live_url),
            "message": "Deployed successfully!",
            "invitation": data,
        })
