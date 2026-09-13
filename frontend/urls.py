from django.urls import path
from django.views.generic import TemplateView

from .views import EditorPage

urlpatterns = [
    path("", TemplateView.as_view(template_name="frontend/home.html"), name="home"),
    path("login/", TemplateView.as_view(template_name="frontend/auth.html"), name="login"),
    path("dashboard/", TemplateView.as_view(template_name="frontend/dashboard.html"), name="dashboard"),
    path("templates/", TemplateView.as_view(template_name="frontend/gallery.html"), name="gallery"),
    path("editor/<int:pk>/", EditorPage.as_view(), name="editor"),
    path("pricing/", TemplateView.as_view(template_name="frontend/pricing.html"), name="pricing"),
]
