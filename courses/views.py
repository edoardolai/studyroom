from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from accounts.models import User
from .forms import CourseForm, FeedbackForm, MaterialForm
from .models import Course, CourseMaterial, Enrolment, Feedback, Notification


def can_view_materials(user, course):
    if user.role == User.Role.TEACHER:
        return course.teacher_id == user.pk
    return course.enrolments.filter(student=user, is_blocked=False).exists()


@login_required
@require_safe
def course_list(request):
    courses = Course.objects.select_related("teacher")
    page = Paginator(courses, 12).get_page(request.GET.get("page"))
    return render(request, "courses/course_list.html", {"page": page})


@login_required
@require_safe
def course_detail(request, pk):
    course = get_object_or_404(Course.objects.select_related("teacher"), pk=pk)
    has_access = can_view_materials(request.user, course)
    enrolled = request.user.role == User.Role.STUDENT and has_access
    blocked = course.enrolments.filter(student=request.user, is_blocked=True).exists()
    materials = course.materials.all() if has_access else CourseMaterial.objects.none()
    page = Paginator(materials, 15).get_page(request.GET.get("page"))
    feedback = Paginator(course.feedback.select_related("student"), 10).get_page(request.GET.get("feedback_page"))
    return render(request, "courses/course_detail.html", {
        "course": course, "enrolled": enrolled, "blocked": blocked,
        "has_access": has_access, "page": page, "feedback": feedback,
    })


@login_required
@require_http_methods(["GET", "POST"])
def course_create(request):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            messages.success(request, "Course created.")
            return redirect("courses:detail", pk=course.pk)
    else:
        form = CourseForm()
    return render(request, "courses/course_form.html", {"form": form})


@login_required
@require_POST
@transaction.atomic
def enrol(request, pk):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk)
    enrolment, created = Enrolment.objects.get_or_create(course=course, student=request.user)
    if enrolment.is_blocked:
        raise PermissionDenied("You are blocked from enrolling on this course.")
    if created:
        Notification.objects.create(
            recipient=course.teacher, course=course,
            message=f"{request.user.username} enrolled on {course.title}.",
        )
        messages.success(request, "You are now enrolled.")
    else:
        messages.info(request, "You are already enrolled on this course.")
    return redirect("courses:detail", pk=course.pk)


@login_required
@require_safe
def my_courses(request):
    if request.user.role == User.Role.TEACHER:
        courses = request.user.courses_taught.select_related("teacher")
    else:
        courses = Course.objects.filter(
            enrolments__student=request.user, enrolments__is_blocked=False,
        ).select_related("teacher")
    page = Paginator(courses, 12).get_page(request.GET.get("page"))
    return render(request, "courses/course_list.html", {"page": page, "heading": "My courses"})


@login_required
@require_safe
def roster(request, pk):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    enrolments = course.enrolments.select_related("student").order_by("student__username")
    page = Paginator(enrolments.filter(is_blocked=False), 25).get_page(request.GET.get("page"))
    blocked = Paginator(enrolments.filter(is_blocked=True), 25).get_page(request.GET.get("blocked_page"))
    return render(request, "courses/roster.html", {"course": course, "page": page, "blocked": blocked})


@login_required
@require_http_methods(["GET", "POST"])
def student_manage(request, pk, enrolment_id, action):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    enrolments = course.enrolments.filter(pk=enrolment_id, is_blocked=(action == "unblock"))
    enrolment = get_object_or_404(enrolments.select_related("student"))
    if request.method == "POST":
        if action == "block":
            enrolments.update(is_blocked=True)
            messages.success(request, "Student blocked from this course.")
        else:
            # Lifting a block lets the student choose whether to enrol again.
            enrolments.delete()
            message = "Block lifted. The student can enrol again." if action == "unblock" else "Student removed from this course."
            messages.success(request, message)
        return redirect("courses:roster", pk=course.pk)
    return render(request, "courses/student_confirm.html", {
        "course": course, "enrolment": enrolment, "action": action,
    })


@login_required
@require_http_methods(["GET", "POST"])
def material_upload(request, pk):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    if request.method == "POST":
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.course = course
            material.save()
            messages.success(request, "Material uploaded.")
            return redirect("courses:detail", pk=course.pk)
    else:
        form = MaterialForm()
    return render(request, "courses/material_form.html", {"course": course, "form": form})


@login_required
@require_safe
@never_cache
def material_download(request, pk):
    material = get_object_or_404(CourseMaterial.objects.select_related("course"), pk=pk)
    if not can_view_materials(request.user, material.course):
        raise PermissionDenied
    try:
        file = material.file.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    return FileResponse(file, as_attachment=True, filename=Path(material.file.name).name)


@login_required
@require_http_methods(["GET", "POST"])
def feedback_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.user.role != User.Role.STUDENT or not can_view_materials(request.user, course):
        raise PermissionDenied
    feedback = Feedback.objects.filter(course=course, student=request.user).first()
    if request.method == "POST":
        form = FeedbackForm(request.POST, instance=feedback)
        if form.is_valid():
            Feedback.objects.update_or_create(
                course=course, student=request.user, defaults={"body": form.cleaned_data["body"]},
            )
            messages.success(request, "Feedback saved.")
            return redirect("courses:detail", pk=course.pk)
    else:
        form = FeedbackForm(instance=feedback)
    return render(request, "courses/feedback_form.html", {"course": course, "form": form})


@login_required
@require_safe
def notification_list(request):
    notifications = request.user.notifications.select_related("course")
    page = Paginator(notifications, 20).get_page(request.GET.get("page"))
    return render(request, "courses/notifications.html", {
        "page": page, "unread_count": notifications.filter(is_read=False).count(),
    })


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect("courses:notifications")
