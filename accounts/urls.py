from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html",
    ), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("students/", views.student_list, name="student-list"),
    path("members/", views.member_list, name="member-list"),
    path("members/<int:pk>/", views.profile, name="profile"),
    path("members/<int:pk>/photo/", views.profile_photo, name="profile-photo"),
    path("accounts/profile/edit/", views.profile_edit, name="profile-edit"),
    path("accounts/status/", views.status_add, name="status-add"),
]
