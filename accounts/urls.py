from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginRequestView,
    LoginVerifyView,
    MeView,
    SignupRequestView,
    SignupVerifyView,
)

urlpatterns = [
    path("signup/request-otp/", SignupRequestView.as_view()),
    path("signup/verify-otp/", SignupVerifyView.as_view()),
    path("login/request-otp/", LoginRequestView.as_view()),
    path("login/verify-otp/", LoginVerifyView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("me/", MeView.as_view()),
]
