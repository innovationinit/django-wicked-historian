from typing import (
    Any,
    Dict,
    Iterable,
    Set,
    Tuple,
    Type,
)

from django.apps import apps
from django.core.checks import (
    CheckMessage,
    Error,
    Tags,
    Warning,
    register,
)
from django.conf import settings
from django.db import (
    connection,
    models,
)
from django.db.migrations import operations
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.models import ModelOperation
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState

from .models import BaseEditHistory
from .utils import get_concrete_model_subclasses


Choice = Tuple[Any, str]

check_missing_migration = getattr(settings, 'WICKED_HISTORIAN_RUN_CHECK_MISSING_MIGRATION', True)


@register(Tags.signals)
def check_m2m_registration_for_edit_history(**kwargs) -> Iterable[CheckMessage]:
    messages = []
    for history_model in get_concrete_model_subclasses(BaseEditHistory):
        if not history_model.m2m_signals_registered:
            messages.append(
                Error(
                    "M2M signals are not registered for {} model!".format(history_model.__name__),
                    hint="Add {}.register_m2m_signals call to your AppConfig.ready.".format(history_model.__name__),
                    obj=history_model,
                    id='wicked_historian.E001',
                )
            )
    return messages


@register
def check_incremental_changes_in_field_choices(**kwargs) -> Iterable[CheckMessage]:
    messages = []
    migration_loader = MigrationLoader(None, ignore_no_migrations=True)
    for history_model in get_concrete_model_subclasses(BaseEditHistory):
        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        app_label = history_model._meta.app_label
        if is_any_migration_missing(migration_loader, app_label):
            messages.append(
                Warning(
                    'Cannot check incremental changes in fields - there are changes in the {} app without a migration.'.format(app_label),
                    hint='Run makemigrations management command.',
                    obj=history_model,
                    id='wicked_historian.W001',
                )
            )
        else:
            removed_fields = get_removed_choices(migration_loader.graph, history_model, 'field')
            if removed_fields:
                messages.append(
                    Error(
                        'Detected a removed field: {}'.format(removed_fields),
                        hint='Move the old versions of fields to the `obsolete_field_choices` list.',
                        obj=history_model,
                        id='wicked_historian.E002',
                    )
                )
    return messages


@register
def check_incremental_changes_in_choices_of_fields(**kwargs) -> Iterable[CheckMessage]:
    messages = []
    migration_loader = MigrationLoader(None, ignore_no_migrations=True)
    for history_model in get_concrete_model_subclasses(BaseEditHistory):
        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        history_model_opts = history_model._meta
        app_label = history_model_opts.app_label
        if is_any_migration_missing(migration_loader, app_label):
            messages.append(
                Warning(
                    'Cannot check incremental changes in choices of fields - there are changes in the {} app without a migration.'.format(app_label),
                    hint='Run makemigrations management command.',
                    obj=history_model,
                    id='wicked_historian.W002',
                )
            )
        else:
            tracked_model = history_model_opts.get_field('model').related_model
            # noinspection PyProtectedMember
            # pylint: disable=protected-access
            tracked_model_opts = tracked_model._meta
            for field in tracked_model_opts.fields:
                removed_choices = get_removed_choices(migration_loader.graph, tracked_model, field.name)
                if removed_choices:
                    messages.append(
                        Error(
                            'Detected removed choices of field {}: {}'.format(field.name, removed_choices),
                            hint='Models with history tracking need to have incremental changes in their field choices.',
                            obj=tracked_model,
                            id='wicked_historian.E003',
                        )
                    )
    return messages


def get_removed_choices(migration_graph: MigrationGraph, model: Type[models.Model], field_name: str) -> Set[Choice]:
    # noinspection PyProtectedMember
    # pylint: disable=protected-access
    current_choices = get_current_choices(model, field_name)
    historical_choices = get_all_historical_choices(migration_graph, model, field_name)

    current_choices_values = set(choice[0] for choice in current_choices)
    historical_choices_values = set(choice[0] for choice in historical_choices)
    return historical_choices_values - current_choices_values


def get_current_choices(model: Type[models.Model], field_name: str) -> Set[Choice]:
    model_opts = model._meta
    return set(model_opts.get_field(field_name).choices)


def get_all_historical_choices(migration_graph: MigrationGraph, model: Type[models.Model], field_name: str) -> Set[Choice]:
    # noinspection PyProtectedMember
    # pylint: disable=protected-access
    options = model._meta
    assert field_name in (field.name for field in options.fields), 'Field not found in model fields.'

    app_label = options.app_label
    models_fields_all_choices = get_all_fields_all_historical_choices(migration_graph, app_label)
    # We are iterating though all current fields and since checks are run before making migrations we need to get(field_name, [])
    # so that we don't crash when adding new field without historical choices
    return models_fields_all_choices[model.__name__.lower()].get(field_name, [])


def update_choices_by_model_name_by_field_name(choices_by_model_name_by_field_name: Dict[str, Dict[str, Set[Choice]]], operation: ModelOperation):
    def get_field_choices(model_field: models.Field) -> Set[Choice]:
        return set(model_field.choices or [])

    if isinstance(operation, operations.CreateModel):
        choices_by_model_name_by_field_name[operation.name.lower()] = {}
        for operation_field_name, field in operation.fields:
            choices_by_model_name_by_field_name[operation.name.lower()][operation_field_name] = get_field_choices(field)
    elif isinstance(operation, operations.AddField):
        choices_by_model_name_by_field_name[operation.model_name][operation.name] = get_field_choices(operation.field)
    elif isinstance(operation, operations.AlterField):
        choices_by_model_name_by_field_name[operation.model_name][operation.name] |= get_field_choices(operation.field)
    elif isinstance(operation, operations.RenameField):
        choices_by_model_name_by_field_name[operation.model_name][operation.new_name] = (
            choices_by_model_name_by_field_name[operation.model_name][operation.old_name]
        )
        del choices_by_model_name_by_field_name[operation.model_name][operation.old_name]
    elif isinstance(operation, operations.RenameModel):
        choices_by_model_name_by_field_name[operation.new_name.lower()] = choices_by_model_name_by_field_name[operation.old_name.lower()]
        del choices_by_model_name_by_field_name[operation.old_name.lower()]
    elif isinstance(operation, operations.RemoveField):
        del choices_by_model_name_by_field_name[operation.model_name][operation.name]
    elif isinstance(operation, operations.DeleteModel):
        del choices_by_model_name_by_field_name[operation.name.lower()]


def get_all_fields_all_historical_choices(migration_graph: MigrationGraph, app_label: str) -> Dict[str, Dict[str, Set[Choice]]]:
    choices_by_model_name_by_field_name = {}

    related_app_labels = {k[0] for k, v in migration_graph.nodes.items() if v.app_label == app_label}
    dependencies = [leaf_node for app_label in related_app_labels for leaf_node in migration_graph.leaf_nodes(app_label)]

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(dependencies, clean_start=True)

    for migration, _ in plan:
        if migration.app_label not in related_app_labels:
            continue
        for operation in migration.operations:
            update_choices_by_model_name_by_field_name(choices_by_model_name_by_field_name, operation)

    return choices_by_model_name_by_field_name


class ExceptionRaisingNonInteractiveMigrationQuestioner(NonInteractiveMigrationQuestioner):

    """Custom NonInteractiveMigrationQuestioner that raises an exception instead of calling `sys.exit`."""

    class InteractionNeeded(Exception):
        pass

    def ask_not_null_addition(self, field_name, model_name):
        raise self.InteractionNeeded()

    def ask_auto_now_add_addition(self, field_name, model_name):
        raise self.InteractionNeeded()


def is_any_migration_missing(migration_loader: MigrationLoader, app_label: str) -> bool:
    if not check_missing_migration:
        return False

    if app_label not in is_any_migration_missing.results_cache:
        questioner = ExceptionRaisingNonInteractiveMigrationQuestioner(specified_apps=[app_label], dry_run=True)
        autodetector = MigrationAutodetector(
            migration_loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )
        try:
            changes = autodetector.changes(
                graph=migration_loader.graph,
                trim_to_apps=[app_label],
                convert_apps=[app_label],
                migration_name='check',
            )
        except ExceptionRaisingNonInteractiveMigrationQuestioner.InteractionNeeded:
            is_any_migration_missing.results_cache[app_label] = True
        else:
            is_any_migration_missing.results_cache[app_label] = bool(changes)
    return is_any_migration_missing.results_cache[app_label]


is_any_migration_missing.results_cache = {}  # type: Dict[str, bool]
