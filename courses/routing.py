from django.urls import path

from .consumers import CourseChatConsumer

websocket_urlpatterns = [
    path("ws/courses/<int:pk>/chat/", CourseChatConsumer.as_asgi()),
]
