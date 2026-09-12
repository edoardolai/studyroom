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
    path("<int:pk>/students/<int:enrolment_id>/remove/", views.student_manage,
         {"action": "remove"}, name="student-remove"),
    path("<int:pk>/students/<int:enrolment_id>/block/", views.student_manage,
         {"action": "block"}, name="student-block"),
    path("<int:pk>/students/<int:enrolment_id>/unblock/", views.student_manage,
         {"action": "unblock"}, name="student-unblock"),
    path("<int:pk>/feedback/", views.feedback_edit, name="feedback-edit"),
    path("<int:pk>/materials/new/", views.material_upload, name="material-upload"),
    path("materials/<int:pk>/download/", views.material_download, name="material-download"),
]
