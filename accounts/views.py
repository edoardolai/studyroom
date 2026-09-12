from django.shortcuts import redirect, render

from .forms import RegistrationForm


def index(request):
    return render(request, "accounts/index.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:index")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:index")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})
