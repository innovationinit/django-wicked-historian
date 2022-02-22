from unittest import mock

from django.db.migrations import operations

import wicked_historian.checks as checks

from testapp.models import (
    Book,
    BookEditHistory,
)
from testapp.tests.base import FreezeTimeTestCase


class IncrementalChangesCheckTestCase(FreezeTimeTestCase):
    def tearDown(self):  # pylint: disable=invalid-name
        super().tearDown()
        checks.is_any_migration_missing.results_cache = {}  # clear cache

    def test_get_all_historical_choices(self):
        meta = mock.MagicMock()
        old_field = mock.MagicMock()
        old_field.name = 'existing_field'
        meta.fields = [old_field]
        model = mock.MagicMock()
        model.__name__ = "TestModel"
        model._meta = meta
        migrations_graph = mock.MagicMock()
        with mock.patch(
            'wicked_historian.checks.get_all_fields_all_historical_choices',
            return_value={model.__name__.lower(): {'existing_field': [(2, 'renaissance'), (1, 'medieval')]}}
        ):
            choices = checks.get_all_historical_choices(migrations_graph, model, 'existing_field')
            self.assertEqual(choices, [(2, 'renaissance'), (1, 'medieval')])

        new_field = mock.MagicMock()
        new_field.name = 'new_field'
        meta.fields = [old_field, new_field]
        model_with_new_field = mock.MagicMock()
        model_with_new_field.__name__ = "TestModelWithNewField"
        model_with_new_field._meta = meta
        with mock.patch(
                'wicked_historian.checks.get_all_fields_all_historical_choices',
                return_value={model_with_new_field.__name__.lower(): {'existing_field': [(2, 'renaissance'), (1, 'medieval')]}}
        ):
            choices = checks.get_all_historical_choices(migrations_graph, model_with_new_field, 'new_field')
            self.assertEqual(choices, [])

    def test_is_any_migration_missing__when_no_changes(self):
        interaction_needed = checks.ExceptionRaisingNonInteractiveMigrationQuestioner.InteractionNeeded
        for case, attribute, value, expected in [
                ('no_changes', 'return_value', [], False),
                ('changes', 'return_value', ['some changes'], True),
                ('error', 'side_effect', interaction_needed(), True),
            ]:
            with self.subTest(testing=case), \
                    mock.patch(
                        'wicked_historian.checks.ExceptionRaisingNonInteractiveMigrationQuestioner',
                        InteractionNeeded=interaction_needed,
                        autospec=True
                    ), \
                    mock.patch('wicked_historian.checks.MigrationAutodetector', autospec=True) as migration_autodetector:
                instance = migration_autodetector.return_value
                setattr(instance.changes, attribute, value)

                self.assertEqual(checks.is_any_migration_missing(migration_loader=mock.MagicMock(), app_label='my_app'), expected)
                checks.is_any_migration_missing.results_cache = {}  # clear cache

    def test_check_incremental_changes_in_choices_of_fields__is_any_migration_missing(self):
        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=True):
            messages = [m.id for m in checks.check_incremental_changes_in_choices_of_fields()]
            self.assertListEqual(messages, ['wicked_historian.W002'])

    def test_check_incremental_changes_in_choices_of_fields__detect_removed_choices_moved_to_obsolete(self):  # pylint: disable=invalid-name
        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=False), \
                mock.patch('wicked_historian.checks.get_removed_choices', return_value=[]):
            messages = [m.id for m in checks.check_incremental_changes_in_choices_of_fields()]
            self.assertListEqual(messages, [])

    def test_check_incremental_changes_in_choices_of_fields__detect_removed_choices_not_moved_to_obsolete(self):  # pylint: disable=invalid-name
        def get_removed_choices(migration_graph, model, field_name):  # pylint: disable=unused-argument
            if field_name == 'literary_period':
                return {(4, 'new_age')}
            return []

        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=False), \
                mock.patch('wicked_historian.checks.get_removed_choices', get_removed_choices):
            messages = [m.id for m in checks.check_incremental_changes_in_choices_of_fields()]
            self.assertListEqual(messages, ['wicked_historian.E003'])

    def test_get_removed_choices(self):
        with mock.patch(
            'wicked_historian.checks.get_all_historical_choices',
            return_value={(2, 'renaissance'), (1, 'medieval'), (4, 'new_age'), (3, 'enlightenment')}
        ):
            current_choices = checks.get_current_choices(Book, 'literary_period')
            self.assertSetEqual(current_choices, {(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')})

            obsolete_choices = checks.get_removed_choices(None, Book, 'literary_period')
            self.assertSetEqual(obsolete_choices, {4})

    def test_get_all_fields_all_historical_choices_only_not_interested_app(self):
        migration_graph = mock.MagicMock()
        migration_graph.leaf_nodes.return_value = ['migration1']
        migration_graph.forwards_plan.return_value = [('other_app', 'a_migration_name')]
        choices = checks.get_all_fields_all_historical_choices(migration_graph, 'test_app')
        self.assertFalse(choices, {})

    def test_update_choices_by_model_name_by_field_name_for_create_model(self):
        result = {}
        field = mock.MagicMock(choices={(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')})
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.CreateModel(name='ModelName', fields=[('literary_period', field)]),
        )
        self.assertEqual(result, {'modelname': {'literary_period': {(2, 'renaissance'), (3, 'enlightenment'), (1, 'medieval')}}})

    def test_update_choices_by_model_name_by_field_name_for_add_field(self):
        result = {'modelname': {}}
        field = mock.MagicMock(choices={(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')})
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.AddField(model_name='modelname', name='literary_period', field=field),
        )
        self.assertEqual(result, {'modelname': {'literary_period': {(2, 'renaissance'), (3, 'enlightenment'), (1, 'medieval')}}})

    def test_update_choices_by_model_name_by_field_name_for_alter_field(self):
        result = {'modelname': {'literary_period': {(2, 'renaissance'), (1, 'medieval')}}}
        field = mock.MagicMock(choices={(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')})
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.AlterField(model_name='modelname', name='literary_period', field=field),
        )
        self.assertEqual(result, {'modelname': {'literary_period': {(2, 'renaissance'), (3, 'enlightenment'), (1, 'medieval')}}})

    def test_update_choices_by_model_name_by_field_name_for_rename_field(self):
        result = {'modelname': {'literary_period_old': {(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')}}}
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.RenameField(model_name='modelname', old_name='literary_period_old', new_name='literary_period'),
        )
        self.assertEqual(result, {'modelname': {
            'literary_period': {(2, 'renaissance'), (3, 'enlightenment'), (1, 'medieval')},
        }})

    def test_update_choices_by_model_name_by_field_name_for_rename_model(self):
        result = {'oldmodelname': {'literary_period': {(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')}}}
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.RenameModel(old_name='OldModelName', new_name='ModelName'),
        )
        self.assertEqual(result, {'modelname': {
            'literary_period': {(2, 'renaissance'), (3, 'enlightenment'), (1, 'medieval')},
        }})

    def test_update_choices_by_model_name_by_field_name_for_remove_field(self):
        result = {'modelname': {'literary_period': {(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')}}}
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.RemoveField(model_name='modelname', name='literary_period'),
        )
        self.assertEqual(result, {'modelname': {}})

    def test_update_choices_by_model_name_by_field_name_for_delete_model(self):
        result = {'modelname': {'literary_period': {(2, 'renaissance'), (1, 'medieval'), (3, 'enlightenment')}}}
        checks.update_choices_by_model_name_by_field_name(
            result,
            operations.DeleteModel(name='modelname'),
        )
        self.assertEqual(result, {})

    def test_check_incremental_changes_in_field_choices__is_any_migration_missing(self):
        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=True):
            messages = [m.id for m in checks.check_incremental_changes_in_field_choices()]
            self.assertListEqual(messages, ['wicked_historian.W001'])

    def test_check_incremental_changes_in_field_choices__no_missing_field(self):
        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=False), \
                mock.patch('wicked_historian.checks.get_removed_choices', return_value=[]):
            messages = [m.id for m in checks.check_incremental_changes_in_field_choices()]
            self.assertListEqual(messages, [])

    def test_check_incremental_changes_in_field_choices__missing_field(self):
        with mock.patch('wicked_historian.checks.is_any_migration_missing', return_value=False), \
                mock.patch('wicked_historian.checks.get_removed_choices', return_value=['field_one']):
            messages = [m.id for m in checks.check_incremental_changes_in_field_choices()]
            self.assertListEqual(messages, ['wicked_historian.E002'])
