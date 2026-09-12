from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from accounts.models import User
from .forms import CourseForm, MaterialForm
from .models import Course, CourseMaterial, Enrolment


def can_view_materials(user, course):
    if user.role == User.Role.TEACHER:
        return course.teacher_id == user.pk
    return course.enrolments.filter(student=user).exists()


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
    enrolled = course.enrolments.filter(student=request.user).exists()
    has_access = can_view_materials(request.user, course)
    materials = course.materials.all() if has_access else CourseMaterial.objects.none()
    page = Paginator(materials, 15).get_page(request.GET.get("page"))
    return render(request, "courses/course_detail.html", {
        "course": course, "enrolled": enrolled, "has_access": has_access, "page": page,
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
def enrol(request, pk):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk)
    enrolment, created = Enrolment.objects.get_or_create(course=course, student=request.user)
    if created:
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
        courses = Course.objects.filter(enrolments__student=request.user).select_related("teacher")
    page = Paginator(courses, 12).get_page(request.GET.get("page"))
    return render(request, "courses/course_list.html", {"page": page, "heading": "My courses"})


@login_required
@require_safe
def roster(request, pk):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    enrolments = course.enrolments.select_related("student").order_by("student__username")
    page = Paginator(enrolments, 25).get_page(request.GET.get("page"))
    return render(request, "courses/roster.html", {"course": course, "page": page})


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
