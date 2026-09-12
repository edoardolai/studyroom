from django.contrib import admin

from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "created_at")
    search_fields = ("title", "teacher__username")
    readonly_fields = ("created_at",)
