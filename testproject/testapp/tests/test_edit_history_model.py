import io
import operator
from datetime import (
    time,
    timedelta,
)
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Union,
)

from django.contrib.auth.models import User
from django.core.files import File
from django.db import transaction
from django.db.models.signals import pre_save
from django.test import TransactionTestCase

from wicked_historian.signals_exclusion import signal_exclusion
from wicked_historian.usersmuggler import usersmuggler

from testapp.factories import (
    BookIllegalDownloadFactory,
    BookFactory,
    BookPrintingActionFactory,
    BookShelfSlotFactory,
    ChapterFactory,
    PirateFactory,
    PrinterFactory,
)
from testapp.models import (
    Author,
    Book,
    BookEditHistory,
    BookIllegalDownload,
    BookPrintingAction,
    Chapter,
    Language,
    Pirate,
)
from testapp.tests.base import FreezeTimeTestCase


HistoryEntry = ModelValues = Dict[str, Any]  # pylint: disable=invalid-name


class EditHistoryModelTestCase(FreezeTimeTestCase):

    maxDiff = None

    def setUp(self):  # pylint: disable=invalid-name
        super().setUp()

        # test languages
        self.english = Language.objects.create(name='english')
        self.polish = Language.objects.create(name='polish')

        # test authors
        self.william_shakespeare = Author.objects.create(name='William Shakespeare')
        self.john_paul_ii = Author.objects.create(name='John Paul II')
        self.nostradamus = Author.objects.create(name='Nostradamus')

        # test book shelf slots
        self.slot_1_1 = BookShelfSlotFactory(shelf_number=1, slot_number=1)
        self.slot_2_2 = BookShelfSlotFactory(shelf_number=2, slot_number=2, book_shelf=self.slot_1_1.book_shelf)

        self.user = User.objects.create(username='john.smith')
        with usersmuggler.set_user(self.user):
            self.book = BookFactory(  # type: Book
                title='Macbeth',
                issue_year=1603,
                language=self.english,
                has_pictures=False,
                literary_period=2,
                date_of_publication=(self.frozen_time + timedelta(days=1)).date(),
                moment_of_appearance_on_torrents=self.frozen_time + timedelta(hours=1),
                ebook_length=timedelta(days=1, hours=3, minutes=12, seconds=7),
                number_of_downloads_on_torrents=1223372036854775808,
                encrypted_book=b'some_data',
                cash_lost_because_of_piracy=Decimal('666666666.66'),
                plain_text='foo',
                first_download_hour=time(hour=1),
                book_shelf_slot=self.slot_1_1,
            )
            self.book.authors.set([self.william_shakespeare])
        # just to reset any instance attributes used for creating history
        self.book = Book.objects.get(pk=self.book.pk)  # type: Book
        BookEditHistory.objects.filter(model=self.book).delete()

    def test_getting_history_for_new_model_instance(self):
        with usersmuggler.set_user(self.user):
            self.book = BookFactory()  # type: Book
            self.book.authors.set([self.william_shakespeare])
        self.assertListEqual(BookEditHistory.get_for(self.book), [
            {
                'change_date': self.frozen_time,
                'field_verbose_name': 'authors',
                'new_value': [{'pk': self.william_shakespeare.pk, 'str': str(self.william_shakespeare)}],
                'old_value': [],
                'user': self.user,
            },
        ])

    def test_getting_history_after_adding__many_to_many(self):
        with usersmuggler.set_user(self.user):
            expected_history_entry1, expected_model_values1 = self.add_book_author_and_get_expected_history_result(self.john_paul_ii)
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry1])
        self.assertLastBookEditHistoryValues(expected_model_values1)

        # the last history entry for the authors field is expected to be extended after further modification is made
        with usersmuggler.set_user(self.user):
            expected_history_entry2, expected_model_values2 = self.add_book_author_and_get_expected_history_result(self.nostradamus)
        expected_history_entry2['old_value'] = expected_history_entry1['old_value']
        expected_model_values2['old_value'] = expected_model_values1['old_value']
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry2])
        self.assertLastBookEditHistoryValues(expected_model_values2)

    def add_book_author_and_get_expected_history_result(self, author) -> Tuple[HistoryEntry, ModelValues]:
        def get_authors():
            return [{'pk': _author.pk, 'str': str(_author)} for _author in self.book.authors.all()]

        authors = get_authors()
        self.book.authors.add(author)
        new_authors = get_authors()
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'authors',
            'old_value': authors,
            'new_value': new_authors,
        }
        model_values = {
            'field': '9f06438fcf5e2f6c1b4dfcd0f0fd2383582708c2',
            'old_value': authors,
            'new_value': new_authors,
        }

        return history_entry, model_values

    def test_getting_history_after_removing__many_to_many(self):
        with usersmuggler.set_user(self.user):
            expected_history_entry1, expected_model_values1 = self.remove_book_author_and_get_expected_history_result()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry1])
        self.assertLastBookEditHistoryValues(expected_model_values1)

    def remove_book_author_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.authors.remove(self.william_shakespeare)
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'authors',
            'old_value': [{'pk': self.william_shakespeare.pk, 'str': str(self.william_shakespeare)}],
            'new_value': [],
        }
        model_values = {
            'field': '9f06438fcf5e2f6c1b4dfcd0f0fd2383582708c2',
            'old_value': [{'pk': self.william_shakespeare.pk, 'str': str(self.william_shakespeare)}],
            'new_value': [],
        }

        return history_entry, model_values

    def test_getting_history_after_modification__many_to_many_custom_through(self):
        with usersmuggler.set_user(self.user):
            first_pirate = PirateFactory(name='first_pirate')  # type: Pirate
            first_illegal_download = BookIllegalDownloadFactory(book=self.book, pirate=first_pirate)  # type: BookIllegalDownload

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            first_illegal_download = BookIllegalDownload.objects.get(pk=first_illegal_download.pk)  # not to refresh but to reset private fields
            first_illegal_download.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [],
                    'old_value': [{'pk': first_pirate.pk, 'str': str(first_pirate)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            second_pirate = PirateFactory(name='second_pirate')  # type: Pirate
            BookIllegalDownloadFactory(book=self.book, pirate=second_pirate)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [{'pk': second_pirate.pk, 'str': str(second_pirate)}],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [],
                    'old_value': [{'pk': first_pirate.pk, 'str': str(first_pirate)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            BookIllegalDownloadFactory(book=self.book, pirate=first_pirate)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'old_value': [{'pk': second_pirate.pk, 'str': str(second_pirate)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [],
                    'old_value': [{'pk': first_pirate.pk, 'str': str(first_pirate)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_getting_history_after_modification__many_to_many_custom_through__model_signal_exclusion(self):
        """Test functionality of signals exclusion."""
        with usersmuggler.set_user(self.user):
            first_pirate = PirateFactory(name='first_pirate')  # type: Pirate
            second_pirate = PirateFactory(name='second_pirate')  # type: Pirate
            with signal_exclusion.model_signals_exclusion_context(Book, self.book.pk, 'pirates'):
                first_illegal_download = BookIllegalDownloadFactory(book=self.book, pirate=first_pirate)  # type: BookIllegalDownload

            self.assertNewHistoryEntriesEqual(self.book, [])

            second_illegal_download = BookIllegalDownloadFactory(book=self.book, pirate=second_pirate)  # type: BookIllegalDownload

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'old_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            first_illegal_download = BookIllegalDownload.objects.get(pk=first_illegal_download.pk)  # type: BookIllegalDownload
            with signal_exclusion.model_signals_exclusion_context(Book, self.book.pk, 'pirates'):
                first_illegal_download.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'old_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            second_illegal_download = BookIllegalDownload.objects.get(pk=second_illegal_download.pk)  # type: BookIllegalDownload
            second_illegal_download.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [],
                    'old_value': [
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'pirates',
                    'new_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                        {'pk': second_pirate.pk, 'str': str(second_pirate)},
                    ],
                    'old_value': [
                        {'pk': first_pirate.pk, 'str': str(first_pirate)},
                    ],
                    'user': self.user,
                },
            ])

    def test_getting_history_after_modification__many_to_many_through_fields(self):
        with usersmuggler.set_user(self.user):
            first_printer = PrinterFactory(name='first_printer')
            second_printer = PrinterFactory(name='second_printer')
            first_printing_action = BookPrintingActionFactory(book=self.book, printer=first_printer)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            first_printing_action = BookPrintingAction.objects.get(pk=first_printing_action.pk)  # not to refresh but to reset private fields
            first_printing_action.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            BookPrintingActionFactory(book=self.book, printer=second_printer)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            BookPrintingActionFactory(book=self.book, printer=first_printer)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [{'pk': second_printer.pk, 'str': str(second_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_getting_history_after_modification__many_to_many_through_fields__model_signal_exclusion(self):
        """Test functionality of signals exclusion."""
        with usersmuggler.set_user(self.user):
            first_printer = PrinterFactory(name='first_printer')
            second_printer = PrinterFactory(name='second_printer')
            with signal_exclusion.model_signals_exclusion_context(Book, self.book.pk, 'printers'):
                first_printing_action = BookPrintingActionFactory(book=self.book, printer=first_printer)  # type: BookPrintingAction

            self.assertNewHistoryEntriesEqual(self.book, [])

            second_printing_action = BookPrintingActionFactory(book=self.book, printer=second_printer)  # type: BookPrintingAction

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            first_printing_action = BookPrintingAction.objects.get(pk=first_printing_action.pk)  # not to refresh but to reset private fields
            with signal_exclusion.model_signals_exclusion_context(Book, self.book.pk, 'printers'):
                first_printing_action.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)  # not to refresh but to reset private fields
            second_printing_action = BookPrintingAction.objects.get(pk=second_printing_action.pk)  # not to refresh but to reset private fields
            second_printing_action.delete()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                        {'pk': second_printer.pk, 'str': str(second_printer)},
                    ],
                    'old_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'user': self.user,
                },
            ])

    def test_reset_custom_m2m(self):
        with usersmuggler.set_user(self.user):
            first_printer = PrinterFactory(name='first_printer')
            first_printing_action = BookPrintingActionFactory(book=self.book, printer=first_printer)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            new_book = BookFactory()
            first_printing_action = BookPrintingAction.objects.get(pk=first_printing_action.pk)  # not to refresh but to reset private fields
            first_printing_action.book = new_book
            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.book = Book.objects.get(pk=self.book.pk)
            first_printing_action = BookPrintingAction.objects.get(pk=first_printing_action.pk)  # not to refresh but to reset private fields
            first_printing_action.book = self.book
            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            first_printing_action = BookPrintingAction.objects.get(pk=first_printing_action.pk)  # not to refresh but to reset private fields
            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_squashing_history_custom_m2m(self):
        with usersmuggler.set_user(self.user):
            first_printer = PrinterFactory(name='first_printer')
            first_printing_action = BookPrintingActionFactory(book=self.book, printer=first_printer)

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            new_book = BookFactory()
            first_printing_action.book = new_book
            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [
                        {'pk': first_printer.pk, 'str': str(first_printer)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            first_printing_action.book = self.book
            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            first_printing_action.save()

            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [{'pk': first_printer.pk, 'str': str(first_printer)}],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            self.assertNewHistoryEntriesEqual(new_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'printers',
                    'new_value': [],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_reverse_fk(self):
        with usersmuggler.set_user(User.objects.first()):
            chapter = ChapterFactory(book=self.book)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            other_book = BookFactory()
            chapter.book = other_book
            chapter.save()
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            self.assertNewHistoryEntriesEqual(other_book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            second_chapter = ChapterFactory(book=self.book)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            second_chapter_pk = second_chapter.pk
            second_chapter_str = str(second_chapter)
            second_chapter.delete()
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [{'pk': second_chapter_pk, 'str': second_chapter_str}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter_pk, 'str': second_chapter_str},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            new_second_chapter = second_chapter
            new_second_chapter.save()
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [{'pk': new_second_chapter.pk, 'str': str(new_second_chapter)}],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [{'pk': second_chapter_pk, 'str': second_chapter_str}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter_pk, 'str': second_chapter_str},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            third_chapter = ChapterFactory(book=self.book)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [{'pk': new_second_chapter.pk, 'str': str(new_second_chapter)}, {'pk': third_chapter.pk, 'str': str(third_chapter)}],
                    'old_value': [{'pk': new_second_chapter.pk, 'str': str(new_second_chapter)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [{'pk': new_second_chapter.pk, 'str': str(new_second_chapter)}],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [{'pk': second_chapter_pk, 'str': second_chapter_str}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter_pk, 'str': second_chapter_str},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_reverse_nullable_fk(self):
        chapter = ChapterFactory(book=None)  # type: Chapter
        with usersmuggler.set_user(self.user):
            chapter.book = self.book
            chapter.save()
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            second_chapter = ChapterFactory(book=self.book)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [{'pk': chapter.pk, 'str': str(chapter)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])
            second_chapter.book = None
            second_chapter.save()
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [{'pk': chapter.pk, 'str': str(chapter)}],
                    'old_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [{'pk': chapter.pk, 'str': str(chapter)}],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': chapter.pk, 'str': str(chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_reverse_fk__using_related_manager(self):
        error_message = (
            "You can't use related manager method \"{}\" with bulk=True (which is default)"
            " when creating history for \"chapter_set\" field is enabled!"
        )

        with usersmuggler.set_user(User.objects.first()):
            first_chapter = ChapterFactory(book=None)
            second_chapter = ChapterFactory(book=None)
            self.assertNewHistoryEntriesEqual(self.book, [])

            with self.assertRaisesMessage(AssertionError, error_message.format('add')):
                self.book.chapter_set.add(first_chapter, second_chapter)
            with self.assertRaisesMessage(AssertionError, error_message.format('add')):
                self.book.chapter_set.add(first_chapter, second_chapter, bulk=True)

            self.book.chapter_set.add(first_chapter, second_chapter, bulk=False)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            with self.assertRaisesMessage(AssertionError, error_message.format('remove')):
                self.book.chapter_set.remove(first_chapter)
            with self.assertRaisesMessage(AssertionError, error_message.format('remove')):
                self.book.chapter_set.remove(first_chapter, bulk=True)

            self.book.chapter_set.remove(first_chapter, bulk=False)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            with self.assertRaisesMessage(AssertionError, error_message.format('set')):
                self.book.chapter_set.set([first_chapter])
            with self.assertRaisesMessage(AssertionError, error_message.format('set')):
                self.book.chapter_set.set([first_chapter], bulk=True)

            self.book.chapter_set.set([first_chapter], bulk=False)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

            with self.assertRaisesMessage(AssertionError, error_message.format('clear')):
                self.book.chapter_set.clear()
            with self.assertRaisesMessage(AssertionError, error_message.format('clear')):
                self.book.chapter_set.clear(bulk=True)

            self.book.chapter_set.clear(bulk=False)
            self.assertNewHistoryEntriesEqual(self.book, [
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [],
                    'old_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                        {'pk': second_chapter.pk, 'str': str(second_chapter)},
                    ],
                    'old_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'user': self.user,
                },
                {
                    'change_date': self.frozen_time,
                    'field_verbose_name': 'chapter_set',
                    'new_value': [
                        {'pk': first_chapter.pk, 'str': str(first_chapter)},
                    ],
                    'old_value': [],
                    'user': self.user,
                },
            ])

    def test_getting_history_after_modification__foreign_key(self):
        expected_history_entry, expected_model_values = self.change_book_language_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_language_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.language = self.polish
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'language',
            'old_value': {'pk': self.english.pk, 'str': str(self.english)},
            'new_value': {'pk': self.polish.pk, 'str': str(self.polish)},
        }
        model_values = {
            'field': '5c9b3e1e7bdddf3ad10737d47ab592063ca49542',
            'old_value': {'pk': self.english.pk, 'str': str(self.english)},
            'new_value': {'pk': self.polish.pk, 'str': str(self.polish)},
        }

        return history_entry, model_values

    def test_getting_history_after_modification__one_to_one(self):
        with usersmuggler.set_user(self.user):
            expected_history_entry, expected_model_values = self.change_book_shelf_slot_and_get_expected_history_result()
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_shelf_slot_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.book_shelf_slot = self.slot_2_2
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'book shelf slot',
            'new_value': {'pk': self.slot_2_2.pk, 'str': str(self.slot_2_2)},
            'old_value': {'pk': self.slot_1_1.pk, 'str': str(self.slot_1_1)},
        }
        model_values = {
            'field': '0b92a0cfb0e68cec7199c16eb2fb5b016b54aaf6',
            'new_value': {'pk': self.slot_2_2.pk, 'str': str(self.slot_2_2)},
            'old_value': {'pk': self.slot_1_1.pk, 'str': str(self.slot_1_1)},
        }

        return history_entry, model_values

    def test_getting_history_after_modification__char_field(self):
        expected_history_entry, expected_model_values = self.change_book_title_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_title_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.title = 'Romeo and Juliet'
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'title',
            'old_value': 'Macbeth',
            'new_value': 'Romeo and Juliet',
        }
        model_values = {
            'field': '060fd0b449aa0197cb3ea60b3d0c168c9ba82907',
            'old_value': 'Macbeth',
            'new_value': 'Romeo and Juliet',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__integer_field(self):
        expected_history_entry, expected_model_values = self.change_book_issue_year_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_issue_year_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.issue_year = 2018
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'issue year',
            'old_value': 1603,
            'new_value': 2018
        }
        model_values = {
            'field': 'ce06ba6406ec1d70dbf49d249ce8456c574b076c',
            'old_value': 1603,
            'new_value': 2018,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__boolean_field(self):
        expected_history_entry, expected_model_values = self.change_book_has_picture_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_has_picture_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.has_pictures = True
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'has pictures',
            'old_value': False,
            'new_value': True
        }
        model_values = {
            'field': 'a0b181aa0245ba6b1431728c69c1b6e731681293',
            'old_value': False,
            'new_value': True,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__date_field(self):
        expected_history_entry, expected_model_values = self.change_book_date_of_publication_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_date_of_publication_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.date_of_publication = self.frozen_time.date()
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'date of publication',
            'old_value': '2005-04-03',
            'new_value': '2005-04-02'
        }
        model_values = {
            'field': '450590934e07680f5de606e782733a9b15cd8c0b',
            'old_value': '2005-04-03',
            'new_value': '2005-04-02',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__datetime_field(self):
        expected_history_entry, expected_model_values = self.change_book_moment_of_appearance_on_torrents_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_moment_of_appearance_on_torrents_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.moment_of_appearance_on_torrents = self.frozen_time

        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'moment of appearance on torrents',
            'old_value': '2005-04-02T20:37:00+00:00',
            'new_value': '2005-04-02T19:37:00+00:00',
        }
        model_values = {
            'field': 'e67f1c219d2da439e7e69ec4fd005257c7c8e6bc',
            'old_value': '2005-04-02T20:37:00+00:00',
            'new_value': '2005-04-02T19:37:00+00:00',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__timedelta_field(self):
        expected_history_entry, expected_model_values = self.change_ebook_length_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_ebook_length_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        ebook_length = timedelta(days=1, hours=3, minutes=12, seconds=6)
        self.book.ebook_length = ebook_length
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'ebook length',
            'old_value': 97927000,
            'new_value': 97926000
        }
        model_values = {
            'field': 'f9ee7df21e32f884d6e96f03c7976140e8daa60f',
            'old_value': 97927000,
            'new_value': 97926000,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__biginteger_field(self):
        expected_history_entry, expected_model_values = self.change_book_number_of_downloads_on_torrents_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_number_of_downloads_on_torrents_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.number_of_downloads_on_torrents = 1223372036854775807
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'number of downloads on torrents',
            'old_value': 1223372036854775808,
            'new_value': 1223372036854775807,
        }
        model_values = {
            'field': 'b6bf059d6b5e803ffd5dd75307c01bcdabfa96b2',
            'old_value': 1223372036854775808,
            'new_value': 1223372036854775807,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__file_field(self):
        expected_history_entry, expected_model_values = self.set_book_text_as_pdf_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def set_book_text_as_pdf_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.text_as_pdf = File(io.StringIO('blablabla'), name='other_test_document')
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'text as pdf',
            'old_value': '',
            'new_value': 'other_test_document'
        }
        model_values = {
            'field': '4156cdd39b37e020d99336a32ba7d236b705a78d',
            'old_value': '',
            'new_value': 'other_test_document',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__binary_field(self):
        expected_history_entry, expected_model_values = self.change_encrypted_book_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_encrypted_book_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.encrypted_book = b'some_other_data'
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'encrypted book',
            'old_value': 'c29tZV9kYXRh',
            'new_value': 'c29tZV9vdGhlcl9kYXRh',
        }
        model_values = {
            'field': '90a0792c407b45517adab1433eee19e24c24fcf3',
            'old_value': 'c29tZV9kYXRh',
            'new_value': 'c29tZV9vdGhlcl9kYXRh',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__decimal_field(self):
        expected_history_entry, expected_model_values = self.change_book_cash_lost_because_of_piracy_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_cash_lost_because_of_piracy_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.cash_lost_because_of_piracy = Decimal('766666666.66')
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'cash lost because of piracy',
            'old_value': '666666666.66',
            'new_value': '766666666.66',
        }
        model_values = {
            'field': '57337229b0bd5d6fed0e979dfaeb9e58a61a12f9',
            'old_value': '666666666.66',
            'new_value': '766666666.66',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__text_field(self):
        expected_history_entry, expected_model_values = self.change_book_plain_text_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_plain_text_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.plain_text = 'bar'
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'plain text',
            'old_value': 'foo',
            'new_value': 'bar'
        }
        model_values = {
            'field': 'cbf34af4615b07c850b0804e4f8ede8abb882312',
            'old_value': 'foo',
            'new_value': 'bar',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__time_field(self):
        expected_history_entry, expected_model_values = self.change_book_first_download_hour_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_first_download_hour_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.first_download_hour = time(hour=2)
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'first download hour',
            'old_value': '01:00:00',
            'new_value': '02:00:00'
        }
        model_values = {
            'field': '62a3bb688399f104f058bf3ba1e608696f3c9438',
            'old_value': '01:00:00',
            'new_value': '02:00:00',
        }

        return history_entry, model_values

    def test_getting_history_after_modification__field_with_choices(self):
        expected_history_entry, expected_model_values = self.change_book_literary_period_and_get_expected_history_result()
        with usersmuggler.set_user(self.user):
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [expected_history_entry])
        self.assertLastBookEditHistoryValues(expected_model_values)

    def change_book_literary_period_and_get_expected_history_result(self) -> Tuple[HistoryEntry, ModelValues]:
        self.book.literary_period = 1
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'literary period',
            'old_value': 'renaissance',
            'new_value': 'medieval'
        }
        model_values = {
            'field': 'b5402cbba33e2af751a818d323f6bea8d98dc41f',
            'old_value': 2,
            'new_value': 1,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__nullable_field(self):
        with usersmuggler.set_user(self.user):
            expected_history_entry1, expected_model_values = self.change_book_issue_number_and_get_expected_history_result(1)
            self.book.save()
            self.assertLastBookEditHistoryValues(expected_model_values)

            expected_history_entry2, expected_model_values = self.change_book_issue_number_and_get_expected_history_result(None)
            self.book.save()
            self.assertLastBookEditHistoryValues(expected_model_values)

        self.assertNewHistoryEntriesEqual(self.book, [
            expected_history_entry2,
            expected_history_entry1,
        ])

    def change_book_issue_number_and_get_expected_history_result(self, value: Union[None, int]) -> Tuple[HistoryEntry, ModelValues]:
        old_value = self.book.issue_number
        self.book.issue_number = value
        history_entry = {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'issue number',
            'old_value': old_value,
            'new_value': value
        }
        model_values = {
            'field': '35d347903f996e9efd71a2bfd97e627edd05c2c1',
            'old_value': old_value,
            'new_value': value,
        }

        return history_entry, model_values

    def test_getting_history_after_modification__double_save(self):
        with usersmuggler.set_user(self.user):
            self.change_book_issue_year_and_get_expected_history_result()
            self.book.save()
            expected, _ = self.change_book_issue_year_and_get_expected_history_result()
            self.book.save()

        self.assertNewHistoryEntriesEqual(self.book, [expected])

    def test_getting_history_after_modification__many_fields(self):
        Book.objects.filter(pk=self.book.pk).update(issue_number=1)
        self.book.refresh_from_db()
        with usersmuggler.set_user(self.user):
            changes = [
                self.add_book_author_and_get_expected_history_result(self.john_paul_ii)[0],
                self.change_book_language_and_get_expected_history_result()[0],
                self.change_book_issue_year_and_get_expected_history_result()[0],
                self.change_book_literary_period_and_get_expected_history_result()[0],
                self.change_book_issue_number_and_get_expected_history_result(None)[0],
                self.change_book_shelf_slot_and_get_expected_history_result()[0],
            ]
            self.book.save()

        history_entries = sorted(BookEditHistory.get_for(self.book), key=operator.itemgetter('field_verbose_name'))

        self.assertListEqual(history_entries, sorted(changes, key=operator.itemgetter('field_verbose_name')))

    def test_not_creating_history_after_modification__excluded_field(self):
        with usersmuggler.set_user(self.user):
            self.book.description = 'How much wood could a woodchuck chuck ...'
            self.book.save()
        self.assertNewHistoryEntriesEqual(self.book, [])

    def test_deletion_of_model_with_history_with_registered_reverse_fk(self):
        with usersmuggler.set_user(self.user):
            book = BookFactory()
            ChapterFactory(book=book)

            book_pk = book.pk
            book.delete()

            self.assertEqual(BookEditHistory.objects.filter(model_id=book_pk).count(), 0)

    def test_including_pre_save_handler_changes_into_history(self):
        def description_setting_handler(sender, instance: Book, **kwargs):
            instance.title = 'Handler says hi!'
        pre_save.connect(description_setting_handler, sender=Book)
        with usersmuggler.set_user(self.user):
            self.book.save()
        pre_save.disconnect(description_setting_handler)
        self.assertNewHistoryEntriesEqual(self.book, [
            {
                'change_date': self.frozen_time,
                'field_verbose_name': 'title',
                'new_value': 'Handler says hi!',
                'old_value': 'Macbeth',
                'user': self.user,
            },
        ])

    def assertNewHistoryEntriesEqual(self, book: Book, entries: List[Dict[str, Any]]):  # pylint: disable=invalid-name
        new_entries = BookEditHistory.get_for(book)
        self.assertListEqual(new_entries, entries)

    def assertLastBookEditHistoryValues(self, values: Dict[str, Any]):  # pylint: disable=invalid-name
        history = BookEditHistory.objects.order_by('id').last()
        self.assertEqual(history.user, self.user)
        self.assertEqual(history.change_date, self.frozen_time)
        self.assertEqual(history.model, self.book)
        model_values = dict()
        for attr in values.keys():
            model_values[attr] = getattr(history, attr)
        self.assertDictEqual(model_values, values)


class DeletingDiffableHistoryModelTransactionTestCase(TransactionTestCase):

    def test_deleting_diffable_history_model_with_custom_m2m(self):
        with usersmuggler.set_user(user=None):
            book = BookFactory(
                title='Macbeth',
            )
            BookIllegalDownloadFactory(book=book)
            BookPrintingActionFactory(book=book)

        with transaction.atomic(), usersmuggler.set_user(user=None):
            book.delete()

        self.assertEqual(BookEditHistory.objects.count(), 0)
