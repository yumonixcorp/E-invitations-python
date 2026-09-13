from django.urls import path

from .views import (
    DeployInvitationView,
    InvitationDetailView,
    InvitationListCreateView,
    InvitationMediaDeleteView,
    InvitationMediaView,
    InvitationPreviewView,
    TemplateListView,
    TemplateSampleView,
)

urlpatterns = [
    path("templates/", TemplateListView.as_view()),
    path("templates/<int:pk>/sample/", TemplateSampleView.as_view()),
    path("invitations/", InvitationListCreateView.as_view()),
    path("invitations/<int:pk>/", InvitationDetailView.as_view()),
    path("invitations/<int:pk>/media/", InvitationMediaView.as_view()),
    path("invitations/<int:pk>/media/<str:field>/", InvitationMediaDeleteView.as_view()),
    path("invitations/<int:pk>/media/<str:field>/<int:index>/", InvitationMediaDeleteView.as_view()),
    path("invitations/<int:pk>/preview/", InvitationPreviewView.as_view()),
    path("invitations/<int:pk>/deploy/", DeployInvitationView.as_view()),
]
