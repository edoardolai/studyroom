from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import StatusUpdate, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Account role", {"fields": ("role",)}),
        ("Profile", {"fields": ("biography", "photo")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Account role", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)


@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    list_display = ("author", "body", "created_at")
    search_fields = ("author__username", "body")
    readonly_fields = ("created_at",)
