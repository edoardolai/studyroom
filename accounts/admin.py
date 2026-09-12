from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

from .models import StatusUpdate, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Account role", {"fields": ("role",)}),
        ("Profile", {"fields": ("biography", "photo_link", "photo")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Account role", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)
    readonly_fields = ("photo_link",)
    # The default file widget links to /media/, which isn't publicly served.
    formfield_overrides = {models.ImageField: {"widget": forms.FileInput}}

    @admin.display(description="Current photo")
    def photo_link(self, obj):
        if not obj.photo:
            return "No photo"
        url = reverse("accounts:profile-photo", args=[obj.pk])
        return format_html('<a href="{}">View photo</a>', url)


@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    list_display = ("author", "body", "created_at")
    search_fields = ("author__username", "body")
    readonly_fields = ("created_at",)
