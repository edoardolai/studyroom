import json

from channels.auth import get_user
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.sessions.backends.db import SessionStore

from .models import ChatMessage, Course
from .permissions import can_access_course


class CourseChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.course_id = self.scope["url_route"]["kwargs"]["pk"]
        self.group_name = f"course_chat_{self.course_id}"
        if not await self.has_access():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({"type": "history", "messages": await self.history()}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not await self.has_access():
            await self.close(code=4403)
            return
        try:
            if text_data is None or len(text_data) > 16000:
                raise ValueError
            data = json.loads(text_data)
            body = data.get("body") if isinstance(data, dict) else None
            if not isinstance(body, str) or not 1 <= len(body.strip()) <= 1000:
                raise ValueError
        except (ValueError, TypeError):
            await self.send(text_data=json.dumps({"type": "error", "message": "Write a message of 1–1000 characters."}))
            return
        message = await self.save_message(body.strip())
        await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "message": message})

    async def chat_message(self, event):
        if not await self.has_access():
            await self.close(code=4403)
            return
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))

    async def has_access(self):
        # Reload the session so logout in another tab also takes effect here.
        session = SessionStore(session_key=self.scope["session"].session_key)
        self.user = await get_user({"session": session})
        return await self.course_access()

    @database_sync_to_async
    def course_access(self):
        course = Course.objects.filter(pk=self.course_id).first()
        return course is not None and can_access_course(self.user, course)

    def message_data(self, message):
        return {
            "id": message.pk, "author": message.author.username,
            "body": message.body, "created_at": message.created_at.isoformat(),
        }

    @database_sync_to_async
    def history(self):
        messages = ChatMessage.objects.filter(course_id=self.course_id).select_related("author").order_by("-pk")[:50]
        return [self.message_data(message) for message in reversed(list(messages))]

    @database_sync_to_async
    def save_message(self, body):
        message = ChatMessage.objects.create(course_id=self.course_id, author=self.user, body=body)
        return self.message_data(message)
