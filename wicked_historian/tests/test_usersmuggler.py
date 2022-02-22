# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from django.test.testcases import TestCase

from wicked_historian.usersmuggler import (
    NoUserSetException,
    usersmuggler,
)


class UserSmugglerTestCase(TestCase):

    def test_no_user_has_been_specified(self):
        with self.assertRaises(NoUserSetException):
            usersmuggler.get_user()

    def test_none_has_been_specified_instead_of_user(self):
        with usersmuggler.set_user(user=None):
            self.assertIsNone(usersmuggler.get_user())

    def test_user_has_been_specified(self):
        test_user = User()

        with usersmuggler.set_user(user=test_user):
            self.assertEqual(usersmuggler.get_user(), test_user)

    def test_several_users_have_been_specified(self):
        test_user1 = User()
        test_user2 = User()

        with usersmuggler.set_user(user=test_user1):
            with usersmuggler.set_user(user=None):
                with usersmuggler.set_user(user=test_user2):
                    self.assertEqual(usersmuggler.get_user(), test_user2)
                self.assertIsNone(usersmuggler.get_user())
            self.assertEqual(usersmuggler.get_user(), test_user1)
