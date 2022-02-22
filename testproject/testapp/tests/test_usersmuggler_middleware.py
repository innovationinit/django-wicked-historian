from django.contrib.auth.models import AnonymousUser
from django.http import (
    HttpRequest,
    JsonResponse,
)
from django.test import TestCase
from django.urls import reverse

from wicked_historian.usersmuggler import (
    NoUserSetException,
    UserSmugglerMiddleware,
)

from testapp.factories import UserFactory


class UserSmugglerMiddlewareTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = UserFactory(username='test_user')

    def test_usersmuggler_middleware__authenticated_user(self):
        self.client.force_login(self.user)
        response_json = self.client.get(reverse('usersmuggler-middleware-test')).json()
        self.assertDictEqual(response_json, {'username': 'test_user'})

    def test_usersmuggler_middleware__anonymous_user(self):
        response_json = self.client.get(reverse('usersmuggler-middleware-test')).json()
        self.assertDictEqual(response_json, {'username': ''})

    def test_usersmugglermiddleware_unit_way(self):
        self._assert_usersmuggler_not_set()
        request = HttpRequest()
        request.user = self.user
        middleware = UserSmugglerMiddleware(self._dummy_get_response)
        json_response = middleware(request)
        self.assertEqual(json_response.content, b'{"username": "test_user"}')
        self._assert_usersmuggler_not_set()

    def test_usersmugglermiddleware_unit_way_not_authenticated(self):
        self._assert_usersmuggler_not_set()
        request = HttpRequest()
        request.user = AnonymousUser()
        middleware = UserSmugglerMiddleware(self._dummy_get_response)
        json_response = middleware(request)
        self.assertEqual(json_response.content, b'{"username": ""}')
        self._assert_usersmuggler_not_set()

    def _assert_usersmuggler_not_set(self):
        from wicked_historian.usersmuggler import usersmuggler
        with self.assertRaises(NoUserSetException):
            usersmuggler.get_user()

    def _dummy_get_response(self, _: HttpRequest) -> JsonResponse:
        from wicked_historian.usersmuggler import usersmuggler
        username = ''
        try:
            username = usersmuggler.get_user().get_username()
        except NoUserSetException:
            pass
        return JsonResponse({'username': username})
