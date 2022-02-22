import logging

from collections import namedtuple

from django.apps import apps
from django.db import connection

from wicked_historian.models import BaseEditHistory


SUPPORTED_DATABASES = ('postgresql', 'mysql')


logger = logging.getLogger(__name__)


ViewRow = namedtuple('ViewRow', 'db_table field_id field_name')


def _prepare_view_rows_from_models():  # type: () -> list[ViewRow]
    rows = []

    history_models = [model for model in apps.get_models() if issubclass(model, BaseEditHistory)]
    for model in history_models:
        for field_description in model.FIELDS_DESCRIPTIONS:
            attrs = {
                'db_table': model._meta.db_table,
                'field_id': field_description.id,
                'field_name': field_description.name
            }
            rows.append(ViewRow(**attrs))

    return rows


def _prepare_sql_view_code_from_rows(rows):  # type: (list[ViewRow]) -> (str, list)
    """Compose SQL code along with values to create or update a view for specified rows."""
    fields = ViewRow._fields

    sql_header = 'CREATE OR REPLACE VIEW wicked_historian_managed_fields ({}) AS '.format(', '.join(fields))
    sql_row = 'SELECT ' + ', '.join(['%s'] * len(fields))
    sql = sql_header + ' UNION '.join([sql_row] * len(rows))
    values = [getattr(row, field) for row in rows for field in fields]

    return sql, values


def create_choices_db_view(sender, **kwargs):
    """Create one db view for all wicked historian serviced django models."""
    if connection.vendor not in SUPPORTED_DATABASES:
        logger.warning('Your database is not supported, the view will not be created')
        return

    view_rows = _prepare_view_rows_from_models()
    if not view_rows:
        return

    sql, values = _prepare_sql_view_code_from_rows(view_rows)

    with connection.cursor() as cursor:
        cursor.execute(sql, values)
