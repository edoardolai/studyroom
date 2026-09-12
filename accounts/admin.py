from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class AccountAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Course role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Course role", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)
