from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import UserFactory


class MemberSearchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = UserFactory(role="teacher", first_name="Morgan", last_name="Shaw")
        cls.student = UserFactory(username="alex", first_name="Alex", last_name="Green")
        cls.url = reverse("accounts:member-list")

    def test_teacher_searches_names_and_usernames(self):
        self.client.force_login(self.teacher)
        for query, expected in [("aLeX", self.student), (" alex  GREEN ", self.student),
                                ("SHAW", self.teacher), (self.teacher.username, self.teacher)]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})
                self.assertEqual(list(response.context["page"]), [expected])
                self.assertNotContains(response, expected.email)

    def test_student_can_browse_but_cannot_search(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'role="search"')
        self.assertEqual(self.client.get(self.url, {"q": "Morgan"}).status_code, 403)
