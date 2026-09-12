from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/register/", views.register, name="register"),
]
