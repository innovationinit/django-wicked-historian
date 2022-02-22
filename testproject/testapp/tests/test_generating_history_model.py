from django.db import models
from django.test.testcases import TestCase

from wicked_historian.models import BaseEditHistory
from wicked_historian.utils import (
    FieldDescription,
    ObsoleteFieldDescription,
    ReverseForeignKeyRelation,
    generate_history_class,
)

from testapp.models import Book


class GeneratingHistoryClassTestCase(TestCase):

    def test_building_fields_description__no_excludes__no_obsoletes(self):
        HistoryModel = generate_history_class(Book, __name__, abstract=True)

        self.assertEqual(len(HistoryModel.FIELDS_DESCRIPTIONS), 22)
        self.assertEqual({description.id for description in HistoryModel.FIELDS_DESCRIPTIONS}, {
            FieldDescription.get_field_description_id('id', models.AutoField),
            FieldDescription.get_field_description_id('title', models.CharField),
            FieldDescription.get_field_description_id('description', models.TextField),
            FieldDescription.get_field_description_id('issue_year', models.IntegerField),
            FieldDescription.get_field_description_id('authors', models.ManyToManyField),
            FieldDescription.get_field_description_id('language', models.ForeignKey),
            FieldDescription.get_field_description_id('has_pictures', models.BooleanField),
            FieldDescription.get_field_description_id('date_of_publication', models.DateField),
            FieldDescription.get_field_description_id('moment_of_appearance_on_torrents', models.DateTimeField),
            FieldDescription.get_field_description_id('ebook_length', models.DurationField),
            FieldDescription.get_field_description_id('text_as_pdf', models.FileField),
            FieldDescription.get_field_description_id('literary_period', models.IntegerField),
            FieldDescription.get_field_description_id('issue_number', models.IntegerField),
            FieldDescription.get_field_description_id('number_of_downloads_on_torrents', models.BigIntegerField),
            FieldDescription.get_field_description_id('encrypted_book', models.BinaryField),
            FieldDescription.get_field_description_id('cash_lost_because_of_piracy', models.DecimalField),
            FieldDescription.get_field_description_id('plain_text', models.TextField),
            FieldDescription.get_field_description_id('first_download_hour', models.TimeField),
            FieldDescription.get_field_description_id('book_shelf_slot', models.OneToOneField),
            FieldDescription.get_field_description_id('pirates', models.ManyToManyField),
            FieldDescription.get_field_description_id('printers', models.ManyToManyField),
            FieldDescription.get_field_description_id('chapter_set', ReverseForeignKeyRelation),
        })
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('id').field_instance.__class__, models.AutoField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('title').field_instance.__class__, models.CharField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('description').field_instance.__class__, models.TextField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('issue_year').field_instance.__class__, models.IntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('authors').field_instance.__class__, models.ManyToManyField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('language').field_instance.__class__, models.ForeignKey)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('has_pictures').field_instance.__class__, models.BooleanField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('date_of_publication').field_instance.__class__, models.DateField)
        self.assertIs(
            HistoryModel.get_tracked_field_choice_by_name('moment_of_appearance_on_torrents').field_instance.__class__, models.DateTimeField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('ebook_length').field_instance.__class__, models.DurationField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('text_as_pdf').field_instance.__class__, models.FileField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('literary_period').field_instance.__class__, models.IntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('issue_number').field_instance.__class__, models.IntegerField)
        self.assertIs(
            HistoryModel.get_tracked_field_choice_by_name('number_of_downloads_on_torrents').field_instance.__class__, models.BigIntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('encrypted_book').field_instance.__class__, models.BinaryField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('cash_lost_because_of_piracy').field_instance.__class__, models.DecimalField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('plain_text').field_instance.__class__, models.TextField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('first_download_hour').field_instance.__class__, models.TimeField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('book_shelf_slot').field_instance.__class__, models.OneToOneField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('pirates').field_instance.__class__, models.ManyToManyField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('printers').field_instance.__class__, models.ManyToManyField)

    def test_building_fields_description__exclude_everything_except_id__no_obsoletes(self):
        """Excludes shouldn't have any influence on FIELDS_DESCRIPTIONS but are not tracked."""
        HistoryModel = generate_history_class(Book, __name__, abstract=True, excluded_fields=[
            'title',
            'description',
            'issue_year',
            'authors',
            'language',
            'has_pictures',
            'date_of_publication',
            'moment_of_appearance_on_torrents',
            'ebook_length',
            'text_as_pdf',
            'literary_period',
            'issue_number',
            'number_of_downloads_on_torrents',
            'encrypted_book',
            'cash_lost_because_of_piracy',
            'plain_text',
            'first_download_hour',
            'book_shelf_slot',
        ])

        self.assertEqual(len(HistoryModel.FIELDS_DESCRIPTIONS), 22)
        self.assertEqual({description.id for description in HistoryModel.FIELDS_DESCRIPTIONS}, {
            FieldDescription.get_field_description_id('id', models.AutoField),
            FieldDescription.get_field_description_id('title', models.CharField),
            FieldDescription.get_field_description_id('description', models.TextField),
            FieldDescription.get_field_description_id('issue_year', models.IntegerField),
            FieldDescription.get_field_description_id('authors', models.ManyToManyField),
            FieldDescription.get_field_description_id('language', models.ForeignKey),
            FieldDescription.get_field_description_id('has_pictures', models.BooleanField),
            FieldDescription.get_field_description_id('date_of_publication', models.DateField),
            FieldDescription.get_field_description_id('moment_of_appearance_on_torrents', models.DateTimeField),
            FieldDescription.get_field_description_id('ebook_length', models.DurationField),
            FieldDescription.get_field_description_id('text_as_pdf', models.FileField),
            FieldDescription.get_field_description_id('literary_period', models.IntegerField),
            FieldDescription.get_field_description_id('issue_number', models.IntegerField),
            FieldDescription.get_field_description_id('number_of_downloads_on_torrents', models.BigIntegerField),
            FieldDescription.get_field_description_id('encrypted_book', models.BinaryField),
            FieldDescription.get_field_description_id('cash_lost_because_of_piracy', models.DecimalField),
            FieldDescription.get_field_description_id('plain_text', models.TextField),
            FieldDescription.get_field_description_id('first_download_hour', models.TimeField),
            FieldDescription.get_field_description_id('book_shelf_slot', models.OneToOneField),
            FieldDescription.get_field_description_id('pirates', models.ManyToManyField),
            FieldDescription.get_field_description_id('printers', models.ManyToManyField),
            FieldDescription.get_field_description_id('chapter_set', ReverseForeignKeyRelation),
        })
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('id').field_instance.__class__, models.AutoField)
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('title')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('description')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('issue_year')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('authors')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('language')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('has_pictures')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('date_of_publication')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('moment_of_appearance_on_torrents')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('ebook_length')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('text_as_pdf')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('literary_period')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('issue_number')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('number_of_downloads_on_torrents')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('encrypted_book')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('cash_lost_because_of_piracy')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('plain_text')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('first_download_hour')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('book_shelf_slot')

    def test_building_fields_description__no_excludes__some_obsoletes(self):
        HistoryModel = generate_history_class(Book, __name__, abstract=True, obsolete_field_choices=[
            ObsoleteFieldDescription('description', models.CharField()),
            ObsoleteFieldDescription('number_of_pages', models.IntegerField()),
            ObsoleteFieldDescription('author', models.ForeignKey('testapp.Author', on_delete=models.PROTECT)),
            ObsoleteFieldDescription('languages', models.ManyToManyField('testapp.Language')),
            ObsoleteFieldDescription('age', models.IntegerField()),
        ])

        self.assertEqual(len(HistoryModel.FIELDS_DESCRIPTIONS), 27)
        self.assertEqual({description.id for description in HistoryModel.FIELDS_DESCRIPTIONS}, {
            FieldDescription.get_field_description_id('id', models.AutoField),
            FieldDescription.get_field_description_id('title', models.CharField),
            FieldDescription.get_field_description_id('description', models.TextField),
            FieldDescription.get_field_description_id('issue_year', models.IntegerField),
            FieldDescription.get_field_description_id('authors', models.ManyToManyField),
            FieldDescription.get_field_description_id('language', models.ForeignKey),
            FieldDescription.get_field_description_id('has_pictures', models.BooleanField),
            FieldDescription.get_field_description_id('date_of_publication', models.DateField),
            FieldDescription.get_field_description_id('moment_of_appearance_on_torrents', models.DateTimeField),
            FieldDescription.get_field_description_id('ebook_length', models.DurationField),
            FieldDescription.get_field_description_id('text_as_pdf', models.FileField),
            FieldDescription.get_field_description_id('literary_period', models.IntegerField),
            FieldDescription.get_field_description_id('issue_number', models.IntegerField),
            FieldDescription.get_field_description_id('number_of_downloads_on_torrents', models.BigIntegerField),
            FieldDescription.get_field_description_id('encrypted_book', models.BinaryField),
            FieldDescription.get_field_description_id('cash_lost_because_of_piracy', models.DecimalField),
            FieldDescription.get_field_description_id('plain_text', models.TextField),
            FieldDescription.get_field_description_id('first_download_hour', models.TimeField),
            FieldDescription.get_field_description_id('book_shelf_slot', models.OneToOneField),
            FieldDescription.get_field_description_id('description', models.CharField),
            FieldDescription.get_field_description_id('number_of_pages', models.IntegerField),
            FieldDescription.get_field_description_id('author', models.ForeignKey),
            FieldDescription.get_field_description_id('languages', models.ManyToManyField),
            FieldDescription.get_field_description_id('age', models.IntegerField),
            FieldDescription.get_field_description_id('pirates', models.ManyToManyField),
            FieldDescription.get_field_description_id('printers', models.ManyToManyField),
            FieldDescription.get_field_description_id('chapter_set', ReverseForeignKeyRelation),
        })
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('id').field_instance.__class__, models.AutoField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('title').field_instance.__class__, models.CharField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('description').field_instance.__class__, models.TextField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('issue_year').field_instance.__class__, models.IntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('authors').field_instance.__class__, models.ManyToManyField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('language').field_instance.__class__, models.ForeignKey)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('has_pictures').field_instance.__class__, models.BooleanField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('date_of_publication').field_instance.__class__, models.DateField)
        self.assertIs(
            HistoryModel.get_tracked_field_choice_by_name('moment_of_appearance_on_torrents').field_instance.__class__, models.DateTimeField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('ebook_length').field_instance.__class__, models.DurationField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('text_as_pdf').field_instance.__class__, models.FileField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('literary_period').field_instance.__class__, models.IntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('issue_number').field_instance.__class__, models.IntegerField)
        self.assertIs(
            HistoryModel.get_tracked_field_choice_by_name('number_of_downloads_on_torrents').field_instance.__class__, models.BigIntegerField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('encrypted_book').field_instance.__class__, models.BinaryField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('cash_lost_because_of_piracy').field_instance.__class__, models.DecimalField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('plain_text').field_instance.__class__, models.TextField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('first_download_hour').field_instance.__class__, models.TimeField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('book_shelf_slot').field_instance.__class__, models.OneToOneField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('pirates').field_instance.__class__, models.ManyToManyField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('printers').field_instance.__class__, models.ManyToManyField)
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('chapter_set').field_instance.__class__, ReverseForeignKeyRelation)
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('number_of_pages')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('author')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('languages')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('age')

    def test_building_fields_description__exclude_everything_except_id__some_obsoletes(self):
        HistoryModel = generate_history_class(Book, __name__, abstract=True, excluded_fields=[
            'title',
            'description',
            'issue_year',
            'authors',
            'language',
            'has_pictures',
            'date_of_publication',
            'moment_of_appearance_on_torrents',
            'ebook_length',
            'text_as_pdf',
            'literary_period',
            'issue_number',
            'number_of_downloads_on_torrents',
            'encrypted_book',
            'cash_lost_because_of_piracy',
            'plain_text',
            'first_download_hour',
            'book_shelf_slot',
        ], obsolete_field_choices=[
            ObsoleteFieldDescription('description', models.CharField()),
            ObsoleteFieldDescription('number_of_pages', models.IntegerField()),
            ObsoleteFieldDescription('author', models.ForeignKey('testapp.Author', on_delete=models.PROTECT)),
            ObsoleteFieldDescription('languages', models.ManyToManyField('testapp.Language')),
            ObsoleteFieldDescription('age', models.IntegerField()),
        ])

        self.assertEqual(len(HistoryModel.FIELDS_DESCRIPTIONS), 27)
        self.assertEqual({description.id for description in HistoryModel.FIELDS_DESCRIPTIONS}, {
            FieldDescription.get_field_description_id('id', models.AutoField),
            FieldDescription.get_field_description_id('title', models.CharField),
            FieldDescription.get_field_description_id('description', models.TextField),
            FieldDescription.get_field_description_id('issue_year', models.IntegerField),
            FieldDescription.get_field_description_id('authors', models.ManyToManyField),
            FieldDescription.get_field_description_id('language', models.ForeignKey),
            FieldDescription.get_field_description_id('has_pictures', models.BooleanField),
            FieldDescription.get_field_description_id('date_of_publication', models.DateField),
            FieldDescription.get_field_description_id('moment_of_appearance_on_torrents', models.DateTimeField),
            FieldDescription.get_field_description_id('ebook_length', models.DurationField),
            FieldDescription.get_field_description_id('text_as_pdf', models.FileField),
            FieldDescription.get_field_description_id('literary_period', models.IntegerField),
            FieldDescription.get_field_description_id('issue_number', models.IntegerField),
            FieldDescription.get_field_description_id('number_of_downloads_on_torrents', models.BigIntegerField),
            FieldDescription.get_field_description_id('encrypted_book', models.BinaryField),
            FieldDescription.get_field_description_id('cash_lost_because_of_piracy', models.DecimalField),
            FieldDescription.get_field_description_id('plain_text', models.TextField),
            FieldDescription.get_field_description_id('first_download_hour', models.TimeField),
            FieldDescription.get_field_description_id('book_shelf_slot', models.OneToOneField),
            FieldDescription.get_field_description_id('description', models.CharField),
            FieldDescription.get_field_description_id('number_of_pages', models.IntegerField),
            FieldDescription.get_field_description_id('author', models.ForeignKey),
            FieldDescription.get_field_description_id('languages', models.ManyToManyField),
            FieldDescription.get_field_description_id('age', models.IntegerField),
            FieldDescription.get_field_description_id('pirates', models.ManyToManyField),
            FieldDescription.get_field_description_id('printers', models.ManyToManyField),
            FieldDescription.get_field_description_id('chapter_set', ReverseForeignKeyRelation),
        })
        self.assertIs(HistoryModel.get_tracked_field_choice_by_name('id').field_instance.__class__, models.AutoField)
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('title')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('description')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('issue_year')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('authors')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('language')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('has_pictures')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('date_of_publication')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('moment_of_appearance_on_torrents')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('ebook_length')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('text_as_pdf')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('literary_period')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('issue_number')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('number_of_downloads_on_torrents')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('encrypted_book')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('cash_lost_because_of_piracy')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('plain_text')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('first_download_hour')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('book_shelf_slot')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('number_of_pages')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('author')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('languages')
        with self.assertRaises(BaseEditHistory.FieldNotTracked):
            HistoryModel.get_tracked_field_choice_by_name('age')
