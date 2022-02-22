import json

from django.contrib.postgres.fields import JSONField as PostgresJSONField

from wicked_historian.encoder import JSONEncoder


__all__ = (
    'JSONField',
)


class JSONField(PostgresJSONField):

    def __init__(self, *args, **kwargs):
        kwargs['encoder'] = kwargs.get('encoder', JSONEncoder)
        super().__init__(*args, **kwargs)

