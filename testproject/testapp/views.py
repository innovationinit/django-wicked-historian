from django.http import (
    HttpRequest,
    JsonResponse,
)

from wicked_historian.usersmuggler import (
    NoUserSetException,
    usersmuggler,
)


def usersmuggler_test_view(_: HttpRequest) -> JsonResponse:
    username = ''
    try:
        username = usersmuggler.get_user().username
    except NoUserSetException:
        pass
    return JsonResponse({'username': username})
