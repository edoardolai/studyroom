from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from accounts.models import User
from .forms import CourseForm
from .models import Course


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
    return render(request, "courses/course_detail.html", {"course": course})


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
