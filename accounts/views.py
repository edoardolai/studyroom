from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from .forms import RegistrationForm
from .models import User


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
