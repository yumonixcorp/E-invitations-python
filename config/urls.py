from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("invitations.urls")),
    path("api/billing/", include("billing.urls")),
    # Template CSS/JS/fonts, loaded by the preview iframe via <base href>.
    re_path(
        r"^library/(?P<path>[\w\-]+/[\w\-./]+\.(?:css|js|png|jpe?g|svg|webp|woff2?))$",
        serve,
        {"document_root": settings.TEMPLATES_LIBRARY_DIR},
    ),
    path("", include("frontend.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
