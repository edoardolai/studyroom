from django.urls import path

from . import api

app_name = "user-api"

urlpatterns = [
    path("users/", api.MemberList.as_view(), name="list"),
    path("users/me/", api.OwnProfile.as_view(), name="me"),
    path("users/<int:pk>/", api.MemberDetail.as_view(), name="detail"),
]
