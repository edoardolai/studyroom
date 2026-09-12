from django.urls import reverse
from rest_framework import serializers

from .models import User


class MemberSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "role", "biography", "photo")
        read_only_fields = fields

    def get_photo(self, user) -> str | None:
        if not user.photo:
            return None
        path = reverse("accounts:profile-photo", args=[user.pk])
        return self.context["request"].build_absolute_uri(path)


class OwnProfileSerializer(MemberSerializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    class Meta(MemberSerializer.Meta):
        fields = MemberSerializer.Meta.fields + ("email",)
        read_only_fields = ("id", "username", "role", "photo", "email")
