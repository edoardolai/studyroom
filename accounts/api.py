from rest_framework import generics

from .models import User
from .serializers import MemberSerializer, OwnProfileSerializer


class MemberList(generics.ListAPIView):
    """List the shared profile fields of active members."""

    queryset = User.objects.filter(is_active=True, is_superuser=False).order_by("username")
    serializer_class = MemberSerializer


class MemberDetail(generics.RetrieveAPIView):
    """Read a member's shared profile. Changes use the me endpoint."""

    queryset = User.objects.filter(is_active=True, is_superuser=False)
    serializer_class = MemberSerializer


class OwnProfile(generics.RetrieveUpdateAPIView):
    """Read your profile or update your name and biography."""

    serializer_class = OwnProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
