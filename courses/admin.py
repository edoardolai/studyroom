from django import forms
from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

from .models import Course, CourseMaterial, Enrolment, Feedback


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


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "updated_at")
    search_fields = ("student__username", "course__title")
    readonly_fields = ("updated_at",)


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "uploaded_at")
    readonly_fields = ("uploaded_at", "course_link")
    formfield_overrides = {models.FileField: {"widget": forms.FileInput}}

    @admin.display(description="Course page")
    def course_link(self, obj):
        if not obj.pk:
            return "Save the material first."
        return format_html('<a href="{}">View course</a>', reverse("courses:detail", args=[obj.course_id]))
