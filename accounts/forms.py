from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        # Teacher accounts are created through the admin.
        fields = ("username", "first_name", "last_name", "email")


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    remove_photo = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "biography", "photo")
        widgets = {
            "biography": forms.Textarea(attrs={"rows": 4}),
            "photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("remove_photo") and "photo" in self.files:
            self.add_error("photo", "Choose a new photo or remove the current one, not both.")
        return data
