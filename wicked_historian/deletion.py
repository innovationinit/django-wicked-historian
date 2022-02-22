import threading
from typing import (
    TYPE_CHECKING,
    Any,
    Tuple,
    Type,
)
from contextlib import contextmanager

if TYPE_CHECKING:
    from django.db.models import Model


class DeletionGuard(threading.local):

    def __init__(self):
        super().__init__()
        self.models_during_deletion = set()

    def start_deletion(self, identifier: Tuple[Type['Model'], Any]):
        self.models_during_deletion.add(identifier)

    def end_deletion(self, identifier: Tuple[Type['Model'], Any]):
        self.models_during_deletion.remove(identifier)

    def create_identifier(self, instance: 'Model') -> Tuple[Type['Model'], Any]:
        return instance.__class__, instance.pk

    def is_instance_during_deletion(self, instance: 'Model') -> bool:
        return self.create_identifier(instance) in self.models_during_deletion

    @contextmanager
    def deletion_context(self, instance: 'Model') -> 'DeletionGuard':
        identifier = self.create_identifier(instance)
        try:
            self.start_deletion(identifier)
            yield self
        finally:
            self.end_deletion(identifier)
