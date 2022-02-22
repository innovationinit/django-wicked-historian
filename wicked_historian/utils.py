import base64
import hashlib
from datetime import (
    date,
    time,
    timedelta,
)
from decimal import Decimal
from functools import (
    singledispatch,
    update_wrapper,
    wraps,
)
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import (  # pylint: disable=unused-import
    Field,
    ManyToOneRel,
    Model,
)
from django.db.models.fields.files import FieldFile
from django.db.models.signals import (
    m2m_changed,
    pre_delete,
    pre_save,
    post_delete,
    post_save,
)
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.module_loading import import_string

from .encoder import JSON_NULL
from .models import (
    BaseEditHistory,
    DiffableHistoryModel,
)
from .signals_exclusion import signal_exclusion
from .usersmuggler import usersmuggler


JSON_FIELD_KWARGS = getattr(settings, 'WICKED_HISTORIAN_JSON_FIELD_KWARGS', {})
json_field_class = import_string(settings.WICKED_HISTORIAN_JSON_FIELD_CLASS)  # type: Type[Field]
FieldValue = TypeVar('FieldValue')
ModelInstanceRepresentation = Dict[str, Any]
ValueRepresentation = Union[FieldValue, ModelInstanceRepresentation, Iterable[ModelInstanceRepresentation]]
ModelDiffItem = Tuple[str, Tuple[Any, Any]]
BaseModel = TypeVar('BaseModel')


class ReverseForeignKeyRelation(Field):
    """
    Class to mark reverse foreign key relations in field value mapper.
    """
    pass


class FieldDescription:
    __slots__ = ['name', 'field_instance']

    def __init__(self, name: str, field_instance: models.Field):
        self.name = name
        if not isinstance(field_instance, models.Field):
            raise ValueError("Field instance must be instance of django's field")
        self.field_instance = field_instance

    @property
    def id(self) -> str:  # pylint: disable=invalid-name
        return self.get_field_description_id(self.name, self.field_instance.__class__)

    @property
    def verbose_name(self) -> str:
        return self.field_instance.verbose_name or self.name

    @staticmethod
    def get_field_description_id(field_name: str, field_class: Type[models.Field]) -> str:
        class_path = field_class.__module__ + "." + field_class.__name__
        field_id = hashlib.sha1('name:{},field_instance:{}'.format(field_name, class_path).encode()).hexdigest()
        return field_id


class ObsoleteFieldDescription(FieldDescription):

    def __init__(self, name: str, field_instance: models.Field):
        super().__init__(name, field_instance)
        self.field_instance.set_attributes_from_name(self.name)


def generate_history_class(
        model_class: Type[DiffableHistoryModel],
        module: str,
        excluded_fields: Optional[Iterable[str]] = None,
        obsolete_field_choices: Optional[List[ObsoleteFieldDescription]] = None,
        abstract: bool = False,
) -> Type[BaseEditHistory]:

    def get_reverse_fk_relations_for_choices():
        return [i for i in getattr(model_class._meta, 'reverse_foreign_key_relations', set())]

    if not issubclass(model_class, DiffableHistoryModel):
        raise ImproperlyConfigured('%s class should inherit from DiffableHistoryModel' % model_class.__name__)
    excluded_fields = excluded_fields or []
    obsolete_field_choices = obsolete_field_choices or []

    fields_from_model = get_field_choices_from_model(model_class)
    reverse_m2m_field_choices = [FieldDescription(x, ReverseForeignKeyRelation()) for x in get_reverse_fk_relations_for_choices()]
    field_choices = fields_from_model + reverse_m2m_field_choices + obsolete_field_choices

    assert len(field_choices) == len(set([f.id for f in field_choices])), 'id (name and type) should be either in model or in obsolete and unique'

    field_choices_by_id = {description.id: description for description in field_choices}
    tracked_fields_choices_by_name = {
        description.name: description
        for description in fields_from_model + reverse_m2m_field_choices
        if description.name not in excluded_fields
    }

    class EditHistory(BaseEditHistory):
        """History of (diffable) model edits"""

        class Meta:
            abstract = True

        model = models.ForeignKey(model_class, on_delete=models.CASCADE)
        user = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            blank=True,
            null=True,
            on_delete=models.PROTECT,
        )
        change_date = models.DateTimeField(default=timezone.now)
        field = models.CharField(
            max_length=40,
            choices=[(description.id, description.verbose_name) for description in field_choices],
        )
        old_value = json_field_class(**JSON_FIELD_KWARGS)
        new_value = json_field_class(**JSON_FIELD_KWARGS)

        FIELD_VALUE_MAPPER = DefaultFieldValueMapper()

        FIELDS_DESCRIPTIONS = field_choices  # Here we want all fields from model (even those excluded) and obsolete
        # Because history may contain entries from field, which become exclueded.

        @classmethod
        def recalculate_choices(cls):
            field_choices = obsolete_field_choices + get_field_choices_from_model(model_class) + reverse_m2m_field_choices
            cls._meta.get_field('field').choices = [(description.id, description.verbose_name) for description in field_choices]

        @classmethod
        def get_for(cls, instance: model_class) -> Iterable[Dict[str, Any]]:
            history_qs = cls.objects.select_related('user').filter(model=instance).order_by('-id')
            history = []
            for entry in history_qs:
                history.append(cls.get_history_entry(entry))
            return history

        @classmethod
        def get_history_entry(cls, entry: 'EditHistory') -> Dict[str, Any]:
            # noinspection PyProtectedMember
            try:
                field = field_choices_by_id[entry.field].field_instance
            except KeyError:
                raise cls.UnknownFieldException('Field \'{}\' is neither in model nor in obsolete fields'.format(entry.field))

            old_value = entry.old_value
            new_value = entry.new_value

            if field.flatchoices:
                old_value = force_text(dict(field.flatchoices).get(old_value, old_value), strings_only=True)
                new_value = force_text(dict(field.flatchoices).get(new_value, new_value), strings_only=True)

            # noinspection PyProtectedMember
            return {
                'user': entry.user,
                'change_date': entry.change_date,
                'field_verbose_name': entry.field_verbose_name,
                'old_value': old_value,
                'new_value': new_value,
            }

        @classmethod
        def get_tracked_field_choice_by_name(cls, name: str) -> FieldDescription:
            try:
                return tracked_fields_choices_by_name[name]
            except KeyError:
                raise cls.FieldNotTracked('Field \'{}\' is not known or is excluded or is obsolete'.format(name))

        @classmethod
        def get_value_representation(cls, name: str, value: FieldValue) -> ValueRepresentation:
            field = cls.get_tracked_field_choice_by_name(name).field_instance
            return cls.FIELD_VALUE_MAPPER(field, value)

        @classmethod
        def create_history(cls, instance: model_class, diff_items: List[ModelDiffItem]):
            # noinspection PyProtectedMember
            # pylint: disable=protected-access
            user = usersmuggler.get_user()
            for field_name, values in diff_items:
                try:
                    old_value = cls.get_value_representation(field_name, values[0])
                    new_value = cls.get_value_representation(field_name, values[1])
                    cls.objects.create(
                        model=instance,
                        field=cls.get_tracked_field_choice_by_name(field_name).id,
                        old_value=old_value,
                        new_value=new_value,
                        user=user,
                    )
                except cls.FieldNotTracked:
                    pass

            # ensure this properties are empty for further m2m checks
            instance._wicked_historian_last_m2m_record = None
            instance._wicked_historian_m2m_changes = {}

        @classmethod
        def create_m2m_history(cls, instance: model_class):
            if model_class.deletion_guard.is_instance_during_deletion(instance):
                return  # Don't trace changes on m2m during instance deletion

            user = usersmuggler.get_user()
            # noinspection PyProtectedMember
            # pylint: disable=protected-access
            m2m_changes = instance._wicked_historian_m2m_changes
            old_fields = m2m_changes['old_value']
            new_fields = m2m_changes['new_value']

            last_m2m_record = getattr(instance, '_wicked_historian_last_m2m_record', None)

            if last_m2m_record and last_m2m_record.field_name == m2m_changes['field_name']:
                last_m2m_record.new_value = new_fields
                last_m2m_record.save(update_fields=['new_value'])
            else:
                try:
                    instance._wicked_historian_last_m2m_record = cls.objects.create(
                        model=instance,
                        field=cls.get_tracked_field_choice_by_name(m2m_changes['field_name']).id,
                        old_value=old_fields,
                        new_value=new_fields,
                        user=user,
                    )
                except cls.FieldNotTracked:
                    pass

        @classmethod
        def m2m_changed(cls, sender: Type[Model], **kwargs):
            # pylint: disable=protected-access

            action = kwargs['action']
            instance = kwargs['instance']

            if '_' in sender.__name__:
                field_name = sender.__name__.split('_', 1)[1]
            else:
                # We gonna retrieve field name the hard way
                model = kwargs['model']
                # noinspection PyProtectedMember
                field_name = [
                    field.name for field in instance._meta.many_to_many if field.remote_field.model == model and field.remote_field.through == sender
                ][0]

            value = list(getattr(instance, field_name).all())

            if action in ['pre_add', 'pre_remove', 'pre_clear']:
                instance._wicked_historian_m2m_changes = {
                    'field_name': field_name,
                    'old_value': cls.get_value_representation(field_name, value)
                }
            elif action in ['post_add', 'post_remove', 'post_clear']:
                instance._wicked_historian_m2m_changes['new_value'] = cls.get_value_representation(field_name, value)
                cls.create_m2m_history(instance)

        @classmethod
        def get_foreign_key_field_name(cls, model_class_for_access_field_name: Type[Model], target_model: Type[Model]) -> Optional[str]:
            for field in model_class_for_access_field_name._meta.get_fields():  # pylint: disable=protected-access
                if (isinstance(field, models.ForeignKey) and
                    (
                            hasattr(field, 'rel') and field.rel.to == target_model or
                            hasattr(field, 'remote_field') and field.remote_field.model == target_model
                    )
                ):
                    return field.name
            return None

        @classmethod
        def get_model_or_none(cls, instance: Model) -> Optional[Model]:
            try:
                return instance.__class__.objects.get(pk=instance.pk)
            except instance.__class__.DoesNotExist:
                return None

        @classmethod
        def custom_through_m2m_handlers_factory(cls, model: Type[Model], m2m_field: Type[Field]) -> Tuple[Callable, Callable]:
            def get_fk_name_to_tracked_model(instance: Model) -> str:
                """Class to retrieve field name. It handles case, when there is more than one FK to same Model in custom through.

                :param instance: custom m2m instance
                :type instance: Model
                :return: field name of custom m2m which refers to current model.
                :rtype: str
                """
                through_field = getattr(model_class, m2m_field.name).rel.through_fields
                if through_field is not None:
                    return through_field[0]
                else:
                    return cls.get_foreign_key_field_name(instance.__class__, model)

            def get_instance_with_tracked_history(through_instance: Model, field_name: str, fresh_through_instance: Model) -> Model:
                instance_with_tracked_history = getattr(fresh_through_instance, field_name)
                # we retrieve an instance from the protected attribute or from the database if there is no data stored for the field
                instance_from_cache = through_instance._wicked_historian_changes_for_related_m2m_models.get(field_name, {}).get(
                    instance_with_tracked_history.pk, {}).get('instance')
                instance_with_tracked_history = instance_from_cache or instance_with_tracked_history
                return instance_with_tracked_history

            def get_m2m_value(instance_with_tracked_history: Model) -> ValueRepresentation:
                related_through_instances = list(getattr(instance_with_tracked_history, m2m_field.name).all())
                return cls.get_value_representation(m2m_field.name, related_through_instances)

            def are_signals_excluded(instance: Model) -> bool:
                """Check if inside model signals exclusion context of this instance and field.

                Used to exclude model signals from handling history creation.
                """
                field_name = get_fk_name_to_tracked_model(instance)
                instance._wicked_historian_changes_for_related_m2m_models = getattr(
                    instance, '_wicked_historian_changes_for_related_m2m_models', {},
                )
                instance_with_tracked_history = get_instance_with_tracked_history(instance, field_name, instance)
                return signal_exclusion.are_model_signals_excluded(model_class, instance_with_tracked_history.pk, m2m_field.name)

            def fill_wicked_historian_changes_for_related_m2m_models(through_instance: Model, fresh_through_instance: Optional[Model]=None):
                # fresh_through_instance is other than through_instance only
                # when custom m2m was pinned from through_instance to fresh_through_instance
                fresh_through_instance = fresh_through_instance or through_instance
                field_name = get_fk_name_to_tracked_model(through_instance)
                through_instance._wicked_historian_changes_for_related_m2m_models = getattr(
                    through_instance, '_wicked_historian_changes_for_related_m2m_models', {},
                )

                instance_with_tracked_history = get_instance_with_tracked_history(through_instance, field_name, fresh_through_instance)
                previous_value = get_m2m_value(instance_with_tracked_history)
                if getattr(instance_with_tracked_history, '_wicked_historian_m2m_changes', {}).get('field_name') != m2m_field.name:
                    instance_with_tracked_history._wicked_historian_m2m_changes = {
                        'field_name': m2m_field.name,
                        'old_value': previous_value,
                    }

                log = through_instance._wicked_historian_changes_for_related_m2m_models
                log.setdefault(field_name, {})
                log[field_name][instance_with_tracked_history.pk] = {
                    'previous_value': previous_value,  # previous value is used to avoid creating transitions to same state
                    'instance': instance_with_tracked_history,
                }

            def pre_action(sender: Type[Model], instance: Model, **kwargs):  # pylint: disable=unused-argument
                if are_signals_excluded(instance):
                    return
                instance_from_db = cls.get_model_or_none(instance)
                # we have to save changes for old and new instance if m2m was pinned from old to new instance
                # if m2m wasn't pinned then operation is idempotent
                fill_wicked_historian_changes_for_related_m2m_models(instance)
                fill_wicked_historian_changes_for_related_m2m_models(instance, instance_from_db)

            def post_action(sender: Type[Model], instance: Model, **kwargs):  # pylint: disable=unused-argument
                if are_signals_excluded(instance):
                    return
                field_name = get_fk_name_to_tracked_model(instance)
                log = instance._wicked_historian_changes_for_related_m2m_models[field_name]
                for pk, value in log.items():
                    instance_with_tracked_history = value['instance']
                    new_value = get_m2m_value(instance_with_tracked_history)
                    by_pk = lambda x: x['pk']
                    if sorted(log[instance_with_tracked_history.pk]['previous_value'], key=by_pk) == sorted(new_value, key=by_pk):
                        continue
                    instance_with_tracked_history._wicked_historian_m2m_changes['new_value'] = new_value
                    cls.create_m2m_history(instance_with_tracked_history)

            return pre_action, post_action

        @classmethod
        def reverse_fk_handlers_factory(cls, field_for_factory: ManyToOneRel) -> Tuple[Callable, Callable]:
            def get_current_value(instance):
                if instance is None:
                    return None, None
                tracked_history_instance = getattr(instance, field_for_factory.field.name)
                if tracked_history_instance is not None:
                    return tracked_history_instance.pk, list(getattr(tracked_history_instance, field_for_factory.get_accessor_name()).all())
                return None, None

            def set_value(instance, record, name):
                pk, value = record
                if pk is not None:
                    instance._previous_values.setdefault(pk, {})[name] = value

            def _fill_previous_values(instance, instance_from_db=None):
                instance_from_db = instance_from_db or instance
                set_value(instance, get_current_value(instance_from_db), 'old_value')

            def pre_action(sender: Type[Model], instance: Model, **kwargs):
                previous_instance_from_db = cls.get_model_or_none(instance)
                instance._previous_values = {}
                instance._previous_instance_from_db = previous_instance_from_db
                _fill_previous_values(instance)
                _fill_previous_values(instance, instance_from_db=previous_instance_from_db)

            def post_action(sender: Type[Model], instance: Model, **kwargs):
                set_value(instance, get_current_value(instance), 'new_value')
                set_value(instance, get_current_value(instance._previous_instance_from_db), 'new_value')
                for pk, data in instance._previous_values.items():
                    try:
                        cls.create_history(
                            field_for_factory.model.objects.get(pk=pk),
                            [(field_for_factory.get_accessor_name(), (data.get('old_value', []), data.get('new_value', [])))],
                        )
                    except field_for_factory.model.DoesNotExist:
                        # Model is already deleted so creating history is not necessary
                        continue

            return pre_action, post_action

        @classmethod
        def register_m2m_signals(cls):
            # noinspection PyProtectedMember
            # pylint: disable=protected-access
            for field in model_class._meta.get_fields():
                if field.many_to_many and not field.auto_created:
                    through_model = getattr(getattr(model_class, field.name), 'through')
                    m2m_changed.connect(
                        cls.m2m_changed,
                        sender=through_model,
                        dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                    )
                    if not through_model._meta.auto_created:
                        pre_function, post_function = cls.custom_through_m2m_handlers_factory(model_class, field)
                        pre_save.connect(
                            pre_function,
                            sender=through_model,
                            weak=False,
                            dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                        )
                        pre_delete.connect(
                            pre_function,
                            sender=through_model,
                            weak=False,
                            dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                        )
                        post_delete.connect(
                            post_function,
                            weak=False,
                            sender=through_model,
                            dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                        )
                        post_save.connect(
                            post_function,
                            sender=through_model,
                            weak=False,
                            dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                        )
                elif (
                    isinstance(field, ManyToOneRel) and
                    field.get_accessor_name() in getattr(model_class._meta, 'reverse_foreign_key_relations', set())
                ):
                    pre_function, post_function = cls.reverse_fk_handlers_factory(field)
                    pre_save.connect(
                        pre_function,
                        sender=field.related_model,
                        weak=False,
                        dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                    )
                    pre_delete.connect(
                        pre_function,
                        sender=field.related_model,
                        weak=False,
                        dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                    )
                    post_delete.connect(
                        post_function,
                        weak=False,
                        sender=field.related_model,
                        dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                    )
                    post_save.connect(
                        post_function,
                        sender=field.related_model,
                        weak=False,
                        dispatch_uid='{}__{}'.format(cls.__name__, field.name),
                    )

                    # Decorate reverse relation descriptor to prevent using manager methods with bulk=True
                    # This methods use update rather than save.

                    related_descriptor = getattr(model_class, field.get_accessor_name())

                    for method_name in ['add', 'clear', 'remove', 'set']:
                        method = getattr(related_descriptor.related_manager_cls, method_name, None)
                        if method is not None:
                            decorated_method = bulk_mode_check(method, field.get_accessor_name())
                            setattr(related_descriptor.related_manager_cls, method_name, decorated_method)



            cls.m2m_signals_registered = True

        def __str__(self) -> str:
            return u'{0} {1} - {2}: {3} => {4}'.format(
                self.user,
                self.change_date.strftime('%Y-%m-%d %H:%M:%S'),
                self.field_name,
                self.old_value,
                self.new_value,
            )

        @property
        def field_verbose_name(self) -> str:
            return field_choices_by_id[self.field].verbose_name

        @property
        def field_name(self) -> str:
            return field_choices_by_id[self.field].name

    attributes = {
        '__module__': module,
    }

    prefix = ''
    if abstract:
        class AbstractMeta(object):
            abstract = True
        attributes['Meta'] = AbstractMeta
        prefix = 'Base'

    return type('%s%sEditHistory' % (prefix, model_class.__name__), (EditHistory, ), attributes)


def method_singledispatch(func: Callable) -> Callable:
    dispatcher = singledispatch(func)

    def wrapper(*args, **kw):
        return dispatcher.dispatch(args[1].__class__)(*args, **kw)

    wrapper.register = dispatcher.register
    update_wrapper(wrapper, func)
    return wrapper


def handle_none_values(func: Callable) -> Callable:
    """Special decorator for wrapping method_singledispatch in DefaultFieldValueMapper."""

    def wrapper(self, field, value):
        if value is None:
            return JSON_NULL
        return func(self, field, value)

    update_wrapper(wrapper, func)
    return wrapper


class DefaultFieldValueMapper:

    @handle_none_values
    @method_singledispatch
    def __call__(self, field: models.Field, value: Any) -> ValueRepresentation:
        return value

    @__call__.register(models.ForeignKey)
    def get_foreign_key_representation(self, field: models.ForeignKey, pk_value: Any) -> ModelInstanceRepresentation:
        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        related_object = field.related_model._default_manager.get(pk=pk_value)
        return self._get_model_instance_representation(related_object)

    @__call__.register(models.ManyToManyField)
    @__call__.register(ReverseForeignKeyRelation)
    def get_many_to_many_field_representation(
            self,
            field: models.ManyToManyField,   # pylint: disable=unused-argument
            instances: Iterable[models.Model]) -> Iterable[ModelInstanceRepresentation]:
        return [self._get_model_instance_representation(instance) for instance in sorted(instances, key=lambda instance: instance.pk)]

    @__call__.register(models.DateField)
    @__call__.register(models.DateTimeField)
    def get_date_representation(self, _: Union[models.DateField, models.DateTimeField], value: date) -> str:
        return value.isoformat()

    @__call__.register(models.DurationField)
    def get_timedelta_representation(self, _: models.DateField, value: timedelta) -> int:
        return int(value.total_seconds() * 1000)

    @__call__.register(models.FileField)
    def get_file_representation(self, _: models.FileField, value: FieldFile) -> str:
        try:
            result = value.url
        except ValueError:
            result = ''
        return result

    @__call__.register(models.BinaryField)
    def get_bytes_representation(self, _: models.BinaryField, value: bytes) -> str:
        return base64.b64encode(value).decode('utf-8')

    @__call__.register(models.DecimalField)
    def get_decimal_representation(self, _: models.DecimalField, value: Decimal) -> str:
        return str(value)

    @__call__.register(models.TimeField)
    def get_time_representation(self, _: models.TimeField, value: time):
        return value.isoformat()

    def _get_model_instance_representation(self, instance: models.Model) -> ModelInstanceRepresentation:
        # noinspection PyProtectedMember
        pk_field = instance._meta.pk  # pylint: disable=protected-access
        return {
            'pk': self(pk_field, instance.pk),
            'str': force_text(instance),
        }


def get_concrete_model_subclasses(model: Type[BaseModel]) -> Iterable[Type[BaseModel]]:
    # noinspection PyProtectedMember
    if not model._meta.abstract:  # pylint: disable=protected-access
        yield model

    for child_model in model.__subclasses__():
        for concrete_child_model in get_concrete_model_subclasses(child_model):
            yield concrete_child_model


def get_field_choices_from_model(model: Type[models.Model]) -> List[FieldDescription]:
    # noinspection PyProtectedMember
    result = []

    for field_instance in model._meta.fields + model._meta.many_to_many:  # pylint: disable=protected-access
        result.append(FieldDescription(field_instance.name, field_instance))

    return result


def bulk_mode_check(func, field_name):
    """Check if bulk kwarg is supplied in func call and have value False."""

    @wraps(func)
    def wraper(*args, **kwargs):
        assert kwargs.get('bulk', True) is False, (
            "You can't use related manager method \"{method_name}\" with bulk=True (which is default)"
            " when creating history for \"{field_name}\" field is enabled!"
        ).format(
            field_name=field_name,
            method_name=func.__name__,
        )
        return func(*args, **kwargs)

    return wraper
