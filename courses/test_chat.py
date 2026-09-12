from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import Client, override_settings
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from studyroom.asgi import application
from .factories import CourseFactory, EnrolmentFactory
from .models import ChatMessage, Enrolment


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class CourseChatTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = CourseFactory()
        cls.student = UserFactory()
        cls.outsider = UserFactory()
        cls.enrolment = EnrolmentFactory(course=cls.course, student=cls.student)

    def setUp(self):
        self.clients = {}
        self.cookies = {}
        for user in (self.course.teacher, self.student, self.outsider):
            client = Client()
            client.force_login(user)
            self.clients[user.pk] = client
            self.cookies[user.pk] = client.cookies["sessionid"].value

    def socket(self, user=None, course=None, origin="http://127.0.0.1:8000"):
        headers = [(b"origin", origin.encode())]
        if user is not None:
            headers.append((b"cookie", f"sessionid={self.cookies[user.pk]}".encode()))
        return WebsocketCommunicator(application, f"/ws/courses/{(course or self.course).pk}/chat/", headers=headers)

    async def test_messages_reach_course_members_and_survive_reconnection(self):
        teacher = self.socket(self.course.teacher)
        student = self.socket(self.student)
        self.assertTrue((await teacher.connect())[0])
        self.assertTrue((await student.connect())[0])
        await teacher.receive_json_from()
        await student.receive_json_from()
        await student.send_json_to({"body": "Can we discuss joins?", "author": self.course.teacher_id})
        received = await teacher.receive_json_from()
        self.assertEqual(received["message"]["author"], self.student.username)
        self.assertEqual(received["message"]["body"], "Can we discuss joins?")
        self.assertEqual(await student.receive_json_from(), received)
        self.assertEqual(await ChatMessage.objects.acount(), 1)
        await student.disconnect()
        student = self.socket(self.student)
        await student.connect()
        history = await student.receive_json_from()
        self.assertEqual(history["messages"], [received["message"]])
        await student.disconnect()
        await teacher.disconnect()

    async def test_anonymous_outsider_and_blocked_student_cannot_connect(self):
        await Enrolment.objects.filter(pk=self.enrolment.pk).aupdate(is_blocked=True)
        for user in (None, self.outsider, self.student):
            with self.subTest(user=user):
                socket = self.socket(user)
                self.assertFalse((await socket.connect())[0])
                await socket.disconnect()

    async def test_invalid_messages_are_rejected_without_saving(self):
        socket = self.socket(self.student)
        await socket.connect()
        await socket.receive_json_from()
        for text in ('not json', '{"body": " "}', '{"body": 123}', '{"body": "' + 'x' * 1001 + '"}'):
            await socket.send_to(text_data=text)
            self.assertEqual((await socket.receive_json_from())["type"], "error")
        self.assertEqual(await ChatMessage.objects.acount(), 0)
        await socket.disconnect()

    async def test_blocked_member_does_not_receive_new_messages_on_open_socket(self):
        teacher = self.socket(self.course.teacher)
        student = self.socket(self.student)
        await teacher.connect()
        await student.connect()
        await teacher.receive_json_from()
        await student.receive_json_from()
        await Enrolment.objects.filter(pk=self.enrolment.pk).aupdate(is_blocked=True)
        await teacher.send_json_to({"body": "Next exercise."})
        self.assertEqual((await teacher.receive_json_from())["type"], "message")
        self.assertEqual(await student.receive_output(), {"type": "websocket.close", "code": 4403})
        await student.disconnect()
        await teacher.disconnect()

    async def test_logout_revokes_existing_socket(self):
        socket = self.socket(self.student)
        await socket.connect()
        await socket.receive_json_from()
        await database_sync_to_async(self.clients[self.student.pk].logout)()
        await socket.send_json_to({"body": "After logout"})
        self.assertEqual(await socket.receive_output(), {"type": "websocket.close", "code": 4403})
        self.assertEqual(await ChatMessage.objects.acount(), 0)
        await socket.disconnect()

    async def test_socket_rejects_untrusted_origin(self):
        socket = self.socket(self.student, origin="https://unrelated.example")
        self.assertFalse((await socket.connect())[0])
        await socket.disconnect()
