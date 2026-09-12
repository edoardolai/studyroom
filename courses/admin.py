from django.contrib import admin

from .models import Course, Enrolment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "created_at")
    search_fields = ("title", "teacher__username")
    readonly_fields = ("created_at",)


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_at")
    search_fields = ("student__username", "course__title")
    readonly_fields = ("enrolled_at",)
