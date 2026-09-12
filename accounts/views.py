from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .forms import ProfileForm, RegistrationForm, StatusUpdateForm
from .models import User
from courses.models import Course


def index(request):
    return render(request, "accounts/index.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:index")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. You can now log in.")
            return redirect("accounts:login")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
@require_safe
def student_list(request):
    if request.user.role != User.Role.TEACHER:
        raise PermissionDenied
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True).order_by("username")
    page = Paginator(students, 25).get_page(request.GET.get("page"))
    return render(request, "accounts/student_list.html", {"page": page})


@login_required
@require_safe
def member_list(request):
    members = User.objects.filter(is_active=True, is_superuser=False).order_by("username")
    query = request.GET.get("q", "").strip()[:150]
    if query:
        if request.user.role != User.Role.TEACHER:
            raise PermissionDenied
        for word in query.split():
            members = members.filter(
                Q(username__icontains=word) | Q(first_name__icontains=word) | Q(last_name__icontains=word)
            )
    page = Paginator(members, 25).get_page(request.GET.get("page"))
    return render(request, "accounts/member_list.html", {"page": page, "query": query})


@login_required
@require_safe
def profile(request, pk):
    member = get_object_or_404(User, pk=pk, is_active=True)
    context = profile_context(member, request.user, StatusUpdateForm(), request.GET.get("page"))
    return render(request, "accounts/profile.html", context)


def profile_context(member, viewer, form, page_number=1):
    page = Paginator(member.status_updates.all(), 10).get_page(page_number)
    courses = Course.objects.none()
    if member.role == User.Role.TEACHER:
        courses = member.courses_taught.all()
    elif member.pk == viewer.pk:
        # A student's enrolments are only shown on their own home page.
        courses = Course.objects.filter(enrolments__student=member)
    return {"member": member, "page": page, "form": form, "courses": courses}


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            if form.cleaned_data["remove_photo"]:
                form.instance.photo = ""
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile", pk=request.user.pk)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
@require_safe
@never_cache
def profile_photo(request, pk):
    member = get_object_or_404(User, pk=pk, is_active=True)
    if not member.photo:
        raise Http404
    try:
        photo = member.photo.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    return FileResponse(photo)


@login_required
@require_POST
def status_add(request):
    form = StatusUpdateForm(request.POST)
    if form.is_valid():
        update = form.save(commit=False)
        # The author comes from the session, never from submitted form fields.
        update.author = request.user
        update.save()
        messages.success(request, "Status posted.")
        return redirect("accounts:profile", pk=request.user.pk)
    return render(request, "accounts/profile.html", profile_context(request.user, request.user, form))
