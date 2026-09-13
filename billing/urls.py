from django.urls import path

from .views import CreateOrderView, PlansView, VerifyPaymentView

urlpatterns = [
    path("plans/", PlansView.as_view()),
    path("order/", CreateOrderView.as_view()),
    path("verify/", VerifyPaymentView.as_view()),
]
