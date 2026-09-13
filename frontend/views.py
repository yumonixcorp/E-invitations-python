from django.views.generic import TemplateView


class EditorPage(TemplateView):
    """Page shell only; data is loaded by editor.js through the JWT-protected API."""
    template_name = "frontend/editor.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invitation_id"] = kwargs["pk"]
        return context
