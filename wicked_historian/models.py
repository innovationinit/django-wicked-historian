import typing
from typing import (
    Any,
    Dict,
    Iterable,
    List,
)

from diffable.models import DiffableModel
from django.db.models import (
    Model,
    fields,
    options,
)
from django.db.models.signals import pre_save
from django.utils.module_loading import import_string

from .deletion import DeletionGuard

if typing.TYPE_CHECKING:
    from .utils import (
        FieldDescription,
        ModelDiffItem,
    )


options.DEFAULT_NAMES = options.DEFAULT_NAMES + ('history_class', 'reverse_foreign_key_relations',)


class DiffableHistoryModel(DiffableModel):

    _wicked_historian_diff_items = None
    deletion_guard = DeletionGuard()

    class Meta:
        abstract = True
        history_class = None

    def save(self, *args, **kwargs):
        if not self._meta.history_class:
            raise NotImplementedError('Specify `history_class` meta property')
        history_class = import_string(self._meta.history_class)
        pre_save_dispatch_uid = 'store_diff_items_{}'.format(id(self))
        pre_save.connect(self.store_diff_items, sender=self.__class__, dispatch_uid=pre_save_dispatch_uid)
        try:
            super(DiffableHistoryModel, self).save(*args, **kwargs)
        finally:
            pre_save.disconnect(dispatch_uid=pre_save_dispatch_uid)
        history_class.create_history(self, diff_items=self._wicked_historian_diff_items)

    def store_diff_items(self, sender, instance, **kwargs):
        """A pre_save signal handler that is going to be attached as the last pre_save handler - stores the diff in the instance."""
        if instance is not self:
            return
        diff_items = list(self.diff.items())
        if not self.pk:
            for field in self._meta.fields:
                if (not self._state.adding and
                        field.name not in self.changed_fields and field.default != fields.NOT_PROVIDED and field.default is not None):
                    diff_items.append(
                        (field.name, (None, field.default))
                    )
        self._wicked_historian_diff_items = diff_items

    def delete(self, using=None, keep_parents=False):
        with self.deletion_guard.deletion_context(self):
            return super(DiffableHistoryModel, self).delete(using=using, keep_parents=keep_parents)


class BaseEditHistory(Model):
    """Base abstract history model for diffable model edits."""

    class Meta:
        abstract = True

    m2m_signals_registered = False

    class UnknownFieldException(Exception):
        pass

    class FieldNotTracked(KeyError):
        pass

    @classmethod
    def get_for(cls, instance: Model) -> Iterable[Dict[str, Any]]:
        raise NotImplementedError()

    @classmethod
    def get_history_entry(cls, entry: 'BaseEditHistory') -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def get_tracked_field_choice_by_name(cls, name: str) -> 'FieldDescription':
        raise NotImplementedError()

    @classmethod
    def get_value_representation(cls, name: str, value: Any) -> Any:
        raise NotImplementedError()

    @classmethod
    def create_history(cls, instance: Model, diff_items: List['ModelDiffItem']):
        raise NotImplementedError()

    @classmethod
    def create_m2m_history(cls, instance: Model):
        raise NotImplementedError()

    @classmethod
    def m2m_changed(cls, sender, **kwargs):
        raise NotImplementedError()

    @classmethod
    def register_m2m_signals(cls):
        raise NotImplementedError()

    def __str__(self) -> str:
        raise NotImplementedError()

    @property
    def field_verbose_name(self) -> str:
        raise NotImplementedError()

    @property
    def field_name(self) -> str:
        raise NotImplementedError()
