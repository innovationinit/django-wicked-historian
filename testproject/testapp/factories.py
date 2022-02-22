from datetime import (
    time,
    timedelta,
)

from django.contrib.auth.models import User

from factory import (
    Sequence,
    SubFactory,
)
from factory.django import DjangoModelFactory

from testapp.models import (
    Book,
    BookIllegalDownload,
    BookPrintingAction,
    BookShelf,
    BookShelfSlot,
    Chapter,
    Language,
    Pirate,
    Printer,
)
from testapp.tests.base import FreezeTimeTestCase


class LanguageFactory(DjangoModelFactory):
    name = Sequence(lambda n: 'Language #%d' % n)

    class Meta:
        model = Language


class UserFactory(DjangoModelFactory):
    username = Sequence(lambda n: 'User #%d' % n)

    class Meta:
        model = User
        django_get_or_create = ('username',)


class BookFactory(DjangoModelFactory):
    issue_year = 2018
    language = SubFactory(LanguageFactory)
    has_pictures = True
    date_of_publication = FreezeTimeTestCase.frozen_time
    moment_of_appearance_on_torrents = FreezeTimeTestCase.frozen_time
    ebook_length = timedelta(hours=3)
    literary_period = 1
    number_of_downloads_on_torrents = 5
    encrypted_book = b'sample_content'
    cash_lost_because_of_piracy = 1000
    plain_text = 'sample_content'
    first_download_hour = time(hour=3, minute=15, second=30)

    class Meta:
        model = Book


class BookShelfFactory(DjangoModelFactory):

    name = Sequence(lambda n: 'Book shelf #%d' % n)

    class Meta:
        model = BookShelf


class BookShelfSlotFactory(DjangoModelFactory):

    book_shelf = SubFactory(BookShelfFactory)
    shelf_number = 1
    slot_number = Sequence(lambda n: n)

    class Meta:
        model = BookShelfSlot


class PirateFactory(DjangoModelFactory):
    name = Sequence(lambda n: 'Pirate #%d' % n)

    class Meta:
        model = Pirate


class BookIllegalDownloadFactory(DjangoModelFactory):
    book = SubFactory(BookFactory)
    pirate = SubFactory(PirateFactory)

    class Meta:
        model = BookIllegalDownload


class PrinterFactory(DjangoModelFactory):
    name = Sequence(lambda n: 'Printer #%d' % n)

    class Meta:
        model = Printer


class BookPrintingActionFactory(DjangoModelFactory):
    book = SubFactory(BookFactory)
    printer = SubFactory(PrinterFactory)
    chef_of_printer = SubFactory(PrinterFactory)

    class Meta:
        model = BookPrintingAction


class ChapterFactory(DjangoModelFactory):
    name = Sequence(lambda n: 'Chapter #%d' % n)
    book = SubFactory(BookFactory)

    class Meta:
        model = Chapter
