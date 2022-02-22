from django.db.models.lookups import (
    Contains,
    Exact,
    GreaterThan,
    GreaterThanOrEqual,
    IExact,
    LessThan,
    LessThanOrEqual,
    Lookup,
)

from django_mysql.models.fields.json import (
    KeyTransform,
    KeyTransformFactory,
)

from .mysql import JSONField as MySQLJSONField

__all__ = (
    'JSONField',
)


class JSONField(MySQLJSONField):
    
    """MySQL JSONField with lookups fixed to work with MariaDB.

    Using MySQLJSONField won't work on MariaDB due to MySQLJSONField creating sql queries with "(CAST(... AS JSON)))", which MariaDB rejects
    as invalid syntax. In order to work around this issue, this JSONField reregisters django_mysql lookups with custom JSONLookupMixin.

    Furthermore, this class supports searching through json arrays with `arrayelements` transform. See KeyTransformWithArrayMemberLookupSupport for
    more information.
    """

    def get_transform(self, name):
        transform = super(JSONField, self).get_transform(name)
        if isinstance(transform, KeyTransformFactory):
            return MyKeyTransformFactory(name)
        if transform:
            return transform  # pragma: no cover

        return MyKeyTransformFactory(name)


class JSONLookupMixin(object):
    
    def get_prep_lookup(self):
        value = self.rhs
        if not hasattr(value, '_prepare') and value is not None and isinstance(value, str):
            return '"{}"'.format(value)
        return super().get_prep_lookup()


@JSONField.register_lookup
class JSONFieldExact(JSONLookupMixin, Exact):
    pass


@JSONField.register_lookup
class JSONFieldIExact(JSONLookupMixin, IExact):
    pass


@JSONField.register_lookup
class JSONFieldContains(JSONLookupMixin, Lookup):
    """Modified version of django_mysql.models.lookups.JSONContains that does not use JSONLookupMixin."""

    lookup_name = 'contains'

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return 'JSON_CONTAINS({}, {})'.format(lhs, rhs), params


@JSONField.register_lookup
class JSONFieldGreaterThan(JSONLookupMixin, GreaterThan):
    pass


@JSONField.register_lookup
class JSONFieldGreaterThanOrEqual(JSONLookupMixin, GreaterThanOrEqual):
    pass


@JSONField.register_lookup
class JSONFieldLessThan(JSONLookupMixin, LessThan):
    pass


@JSONField.register_lookup
class JSONFieldLessThanOrEqual(JSONLookupMixin, LessThanOrEqual):
    pass


class KeyTransformWithArrayMemberLookupSupport(KeyTransform):
    """Custom subclass django_mysql's KeyTransform with support for searching through JSON array elements using wildcard in jsonpath.

    Using arrayelements transform is necessary for searching through JSONFields with arrays inside. You have to use `contains` lookup at the end
    in order to check if any of the elements matches certain value.
    Example:
    >>> ModelCls.objects.create(example_json_field=[{'pk': 1}, {'pk': 2}])
    >>> assert ModelCls.objects.filter(example_json_field__arrayelements__pk__contains=2).count() == 1
    >>> assert ModelCls.objects.filter(example_json_field__arrayelements__pk__contains=3).count() == 0

    """

    list_contains_lookup_name = 'arrayelements'

    def compile_json_path(self, key_transforms):
        path = ['$']
        for key_transform in key_transforms:
            try:
                if key_transform == self.list_contains_lookup_name:
                    path.append('[*]')
                else:
                    num = int(key_transform)
                    path.append('[{}]'.format(num))
            except ValueError:  # non-integer
                path.append('.')
                path.append(key_transform)
        return ''.join(path)


class MyKeyTransformFactory(object):

    def __init__(self, key_name):
        self.key_name = key_name

    def __call__(self, *args, **kwargs):
        return KeyTransformWithArrayMemberLookupSupport(self.key_name, *args, **kwargs)
