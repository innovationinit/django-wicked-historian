import threading
from collections import namedtuple
from contextlib import contextmanager
from typing import (
    Any,
    List,
)


SignalExclusionKey = namedtuple('SignalExclusionKey', ['model_class', 'model_id', 'field_name'])


class SignalExclusion:

    """Object used for signals exclusion."""

    _storage = threading.local()

    @contextmanager
    def model_signals_exclusion_context(self, model_class: Any, model_id: Any, field_name: str):
        """Context in which for supplied "identification" of instance-field pair model signals are marked to be excluded from history handling."""
        try:
            self.store_exclusion_key(model_class, model_id, field_name, 'model_signals')
            yield
        finally:
            self.remove_exclusion_key(model_class, model_id, field_name, 'model_signals')

    def are_model_signals_excluded(self, model_class: Any, model_id: Any, field_name: str) -> bool:
        """Check if model signals for supplied args are excluded."""
        return self.is_exclusion_key_present(model_class, model_id, field_name, 'model_signals')

    def is_exclusion_key_present(self, model_class: Any, model_id: Any, field_name: str, signal_type: str) -> bool:
        """Check if key formed from supplied args is present in store for appropriate signal type."""
        store = self._get_store(signal_type)
        return SignalExclusionKey(model_class, model_id, field_name) in store

    def store_exclusion_key(self, model_class: Any, model_id: Any, field_name: str, signal_type: str):
        """Store key formed from supplied args in store for appropriate signal type."""
        store = self._get_store(signal_type)
        store.insert(0, SignalExclusionKey(model_class, model_id, field_name))

    def remove_exclusion_key(self, model_class: Any, model_id: Any, field_name: str, signal_type: str):
        """Remove key formed from supplied args from store for appropriate signal type."""
        try:
            store = getattr(self._storage, signal_type)
        except AttributeError:
            return
        else:
            store.remove(SignalExclusionKey(model_class, model_id, field_name))

    def _get_store(self, signal_type: str) -> List[SignalExclusionKey]:
        """Get or create store for appropriate signal type."""
        try:
            store = getattr(self._storage, signal_type)
        except AttributeError:
            store = []
            setattr(self._storage, signal_type, store)

        return store


signal_exclusion = SignalExclusion()
