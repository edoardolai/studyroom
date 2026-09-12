from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("new/", views.course_create, name="create"),
    path("mine/", views.my_courses, name="mine"),
    path("<int:pk>/", views.course_detail, name="detail"),
    path("<int:pk>/enrol/", views.enrol, name="enrol"),
    path("<int:pk>/students/", views.roster, name="roster"),
]
