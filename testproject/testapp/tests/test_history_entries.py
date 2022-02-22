"Test history entries for migrated, obsolete fields"
from datetime import (
    time,
    timedelta,
)
from decimal import Decimal
from typing import (
    Any,
    Dict,
)

from django.contrib.auth.models import User
from django.db import models

from wicked_historian.usersmuggler import usersmuggler
from wicked_historian.utils import FieldDescription

from testapp.factories import BookFactory
from testapp.models import (
    Author,
    Book,
    BookEditHistory,
    Language,
    OBSOLETE_BOOK_FIELD_CHOICES,
)
from .base import FreezeTimeTestCase


class GettingHistoryEntriesForChangedFieldsTestCase(FreezeTimeTestCase):
    UNKNOWN_FIELD_ID = 'unknown_field_id'

    def setUp(self):
        super().setUp()

        # test languages
        self.languages = {
            'english': Language.objects.create(name='english'),
            'polish': Language.objects.create(name='polish'),
        }

        # test authors
        self.authors = {
            'william_shakespeare': Author.objects.create(name='William Shakespeare'),
            'john_paul_ii': Author.objects.create(name='John Paul II'),
            'nostradamus': Author.objects.create(name='Nostradamus'),
        }

        self.user = User.objects.create(username='john.smith')
        with usersmuggler.set_user(self.user):
            self.book = BookFactory(  # type: Book
                title='Macbeth',
                issue_year=1603,
                language=self.languages['english'],
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
            )
            self.book.authors.set([self.authors['william_shakespeare']])
        self.book = Book.objects.get(pk=self.book.pk)  # just to reset any instance attributes used for creating history
        self.field_choices_by_name = {description.name: description for description in BookEditHistory.FIELDS_DESCRIPTIONS}
        self.obsolete_field_by_name = {description.name: description for description in OBSOLETE_BOOK_FIELD_CHOICES}
        BookEditHistory.objects.all().delete()

    def test_unknown_field(self):
        self.create_fake_history_entry(
            self.UNKNOWN_FIELD_ID,
            old_value=1603,
            new_value=2018,
        )

        with self.assertRaises(BookEditHistory.UnknownFieldException):
            BookEditHistory.get_for(self.book)

    def test_deleted_field_with_choices(self):
        self.create_fake_history_entry(
            self.obsolete_field_by_name['age'].id,
            old_value=1,
            new_value=2,
        )
        history_entry = self.get_last_history_entry(self.book)
        self.assertDictEqual(history_entry, {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'age',
            'old_value': 'XV',
            'new_value': 'XIX',
        })

    def test_deleted_char_field(self):
        self.create_fake_history_entry(
            self.obsolete_field_by_name['description'].id,
            old_value='abc',
            new_value='xyz',
        )
        history_entry = self.get_last_history_entry(self.book)
        self.assertDictEqual(history_entry, {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'description',
            'old_value': 'abc',
            'new_value': 'xyz',
        })

    def test_deleted_foreign_key_field(self):
        william_shakespeare = {'pk': self.authors['william_shakespeare'].pk, 'str': str(self.authors['william_shakespeare'])}
        john_paul_ii = {'pk': self.authors['john_paul_ii'].pk, 'str': str(self.authors['john_paul_ii'])}
        self.create_fake_history_entry(
            self.obsolete_field_by_name['author'].id,
            old_value=william_shakespeare,
            new_value=john_paul_ii,
        )
        history_entry = self.get_last_history_entry(self.book)
        self.assertDictEqual(history_entry, {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'author',
            'old_value': william_shakespeare,
            'new_value': john_paul_ii,
        })

    def test_deleted_many_to_many_field(self):
        english = {'pk': self.languages['english'].pk, 'str': str(self.languages['english'])}
        polish = {'pk': self.languages['polish'].pk, 'str': str(self.languages['polish'])}
        self.create_fake_history_entry(
            self.obsolete_field_by_name['languages'].id,
            old_value=[english],
            new_value=[english, polish]
        )
        history_entry = self.get_last_history_entry(self.book)
        self.assertDictEqual(history_entry, {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'languages',
            'old_value': [english],
            'new_value': [english, polish]
        })

    def test_different_id_for_different_type_with_the_same_name(self):
        first = FieldDescription('description', models.TextField())
        second = FieldDescription('description', models.CharField())
        third = FieldDescription('description', models.CharField(max_length=50))
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.id, third.id)

    def test_changed_from_string_to_int(self):
        self.create_fake_history_entry(
            self.field_choices_by_name['issue_year'].id,
            old_value='MDCIII',
            new_value='MMXVIII'
        )
        history_entry = self.get_last_history_entry(self.book)
        self.assertDictEqual(history_entry, {
            'change_date': self.frozen_time,
            'user': self.user,
            'field_verbose_name': 'issue year',
            'old_value': 'MDCIII',
            'new_value': 'MMXVIII'
        })

    def test_presence_of_field_names_on_fields_descriptions_list(self):
        field_names = {description.name for description in BookEditHistory.FIELDS_DESCRIPTIONS}
        self.assertEqual(field_names, {
            'age',
            'author',
            'authors',
            'book_shelf_slot',
            'cash_lost_because_of_piracy',
            'date_of_publication',
            'description',
            'ebook_length',
            'encrypted_book',
            'first_download_hour',
            'has_pictures',
            'id',
            'issue_number',
            'issue_year',
            'language',
            'languages',
            'literary_period',
            'moment_of_appearance_on_torrents',
            'number_of_downloads_on_torrents',
            'number_of_pages',
            'plain_text',
            'text_as_pdf',
            'title',
            'pirates',
            'printers',
            'chapter_set',
        })

    @staticmethod
    def get_last_history_entry(book: Book) -> Dict[str, Any]:
        return BookEditHistory.get_for(book)[0]

    def create_fake_history_entry(self, field: str, old_value: Any, new_value: Any) -> BookEditHistory:
        return BookEditHistory.objects.create(**{
            'model': self.book,
            'user': self.user,
            'change_date': self.frozen_time,
            'field': field,
            'old_value': old_value,
            'new_value': new_value
        })
