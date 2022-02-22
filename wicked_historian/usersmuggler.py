import threading
from contextlib import contextmanager
from typing import (
    Callable,
    Optional,
    Union,
)

from django.contrib.auth.base_user import AbstractBaseUser
from django.http import (
    HttpRequest,
    HttpResponse,
)

__all__ = (
    'usersmuggler',
    'NoUserSetException',
    'UserSmugglerMiddleware',
)


class NoUserSetException(Exception):
    pass


class UserSmuggler(object):

    class NotSetType(object):

        """A type for the NOT_SET object."""

    NOT_SET = NotSetType()
    _storage = threading.local()

    @contextmanager
    def set_user(self, user: Optional[AbstractBaseUser]):
        previous_user = self._get_stored_user()
        self._set_stored_user(user)
        try:
            yield
        finally:
            self._set_stored_user(previous_user)

    def get_user(self) -> Optional[AbstractBaseUser]:
        stored_user = self._get_stored_user()

        if stored_user is self.NOT_SET:
            raise NoUserSetException(
                "User was not specified, please use `UserSmuggler.set_user()` context outside of call to `get_user()`.")

        return stored_user

    def _get_stored_user(self) -> Union[AbstractBaseUser, None, NotSetType]:
        try:
            return self._storage.user
        except AttributeError:
            return self.NOT_SET

    def _set_stored_user(self, user: Union[AbstractBaseUser, None, NotSetType]):
        self._storage.user = user


usersmuggler = UserSmuggler()


class UserSmugglerMiddleware:

    """A middleware setting usersmuggler user."""

    def __init__(self, get_response: Callable):
        """Store the get_response callback in the middleware instance."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Set current user in usersmuggler."""
        if request.user.is_authenticated:
            with usersmuggler.set_user(request.user):
                return self.get_response(request)
        return self.get_response(request)
