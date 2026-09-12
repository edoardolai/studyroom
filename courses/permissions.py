from accounts.models import User


def can_access_course(user, course):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.role == User.Role.TEACHER:
        return course.teacher_id == user.pk
    return course.enrolments.filter(student=user, is_blocked=False).exists()
