from django.apps import AppConfig


class TestAppConfig(AppConfig):

    name = 'testapp'

    def ready(self):
        from testapp.models import BookEditHistory
        super().ready()
        BookEditHistory.register_m2m_signals()
