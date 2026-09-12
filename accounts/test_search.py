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

    def test_inactive_and_admin_accounts_are_not_search_results(self):
        UserFactory(first_name="Hidden", is_active=False)
        UserFactory(first_name="Hidden", role="teacher", is_superuser=True)
        self.client.force_login(self.teacher)
        response = self.client.get(self.url, {"q": "Hidden"})
        self.assertEqual(list(response.context["page"]), [])
        self.assertContains(response, "No members to show.")

    def test_student_can_browse_but_cannot_search(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'role="search"')
        self.assertEqual(self.client.get(self.url, {"q": "Morgan"}).status_code, 403)

    def test_search_requires_login(self):
        self.assertEqual(self.client.get(self.url, {"q": "alex"}).status_code, 302)

    def test_empty_search_shows_directory(self):
        self.client.force_login(self.teacher)
        response = self.client.get(self.url, {"q": "   "})
        self.assertEqual(response.context["page"].paginator.count, 2)

    def test_search_pagination_keeps_query(self):
        users = UserFactory.create_batch(26, first_name="Taylor")
        self.client.force_login(self.teacher)
        first = self.client.get(self.url, {"q": "Taylor"})
        second = self.client.get(self.url, {"q": "Taylor", "page": 2})
        self.assertContains(first, '?q=Taylor&amp;page=2')
        self.assertEqual(len(first.context["page"]), 25)
        self.assertEqual(len(second.context["page"]), 1)
        ids = {user.pk for user in first.context["page"]} | {user.pk for user in second.context["page"]}
        self.assertEqual(ids, {user.pk for user in users})

    def test_search_text_is_escaped(self):
        self.client.force_login(self.teacher)
        response = self.client.get(self.url, {"q": '<script>alert("x")</script>'})
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")
