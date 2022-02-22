from django.apps import AppConfig
from django.db.models.signals import post_migrate


class WickedHistorianAppConfig(AppConfig):

    name = 'wicked_historian'

    def ready(self):
        super().ready()
        from . import checks  # noqa
        from wicked_historian.handlers import create_choices_db_view
        post_migrate.connect(create_choices_db_view, sender=self)
