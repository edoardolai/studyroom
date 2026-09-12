from django import forms

from .models import Course, CourseMaterial, Feedback


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("title", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}


class MaterialForm(forms.ModelForm):
    class Meta:
        model = CourseMaterial
        fields = ("title", "file")
        widgets = {"file": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"})}


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ("body",)
        labels = {"body": "Your feedback"}
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}
