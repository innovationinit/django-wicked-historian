import json

from django_mysql.models.fields import JSONField as MySQLJSONField
from wicked_historian.encoder import JSONEncoder


__all__ = (
    'JSONField',
)


class JSONField(MySQLJSONField):

    def __init__(self, *args, **kwargs):
        self.encoder = kwargs.pop('encoder', JSONEncoder)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is not None and not isinstance(value, str):
            return json.dumps(value, cls=self.encoder, allow_nan=False)

        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if not prepared and value is not None:
            return json.dumps(value, cls=self.encoder, allow_nan=False)
        return value
