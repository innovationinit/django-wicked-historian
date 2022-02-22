from django.conf import settings
from django.db import models

from wicked_historian.models import DiffableHistoryModel
from wicked_historian.utils import (
    ObsoleteFieldDescription,
    generate_history_class,
)


class Author(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Book(DiffableHistoryModel):
    title = models.CharField(max_length=100)
    description = models.TextField()
    issue_year = models.IntegerField()
    authors = models.ManyToManyField(Author)
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    has_pictures = models.BooleanField(default=False)
    date_of_publication = models.DateField()
    moment_of_appearance_on_torrents = models.DateTimeField()
    ebook_length = models.DurationField()
    text_as_pdf = models.FileField()
    literary_period = models.IntegerField(choices=[
        (1, 'medieval'),
        (2, 'renaissance'),
        (3, 'enlightenment'),
    ])
    issue_number = models.IntegerField(null=True)
    number_of_downloads_on_torrents = models.BigIntegerField()
    encrypted_book = models.BinaryField()
    cash_lost_because_of_piracy = models.DecimalField(decimal_places=2, max_digits=15)
    plain_text = models.TextField()
    first_download_hour = models.TimeField()
    book_shelf_slot = models.OneToOneField(
        'testapp.BookShelfSlot',
        null=True,
        on_delete = models.CASCADE,
    )
    pirates = models.ManyToManyField('Pirate', through='BookIllegalDownload')
    printers = models.ManyToManyField('Printer', through='BookPrintingAction', through_fields=('book', 'printer'))

    class Meta:
        history_class = 'testapp.models.BookEditHistory'
        reverse_foreign_key_relations = {'chapter_set'}

    def __str__(self):
        return self.title


class BookShelf(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class BookShelfSlot(models.Model):
    book_shelf = models.ForeignKey(BookShelf, on_delete=models.CASCADE)
    shelf_number = models.IntegerField()
    slot_number = models.IntegerField()

    def __str__(self):
        return 'Slot {0.shelf_number}:{0.slot_number} of {0.book_shelf}'.format(self)


class BookPrivateSet(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    books = models.ManyToManyField(Book)

    def __str__(self):
        return self.name


class Pirate(models.Model):
    name = models.CharField(max_length=10)

    def __str__(self) -> str:
        return 'Pirate %s' % self.name


class BookIllegalDownload(models.Model):
    """Model is representing custom through case."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    pirate = models.ForeignKey(Pirate, on_delete=models.CASCADE)
    number_of_downloads = models.IntegerField(default=1)


class Chapter(models.Model):
    name = models.CharField(max_length=10)
    book = models.ForeignKey(Book, null=True, on_delete=models.CASCADE)


class Printer(models.Model):
    name = models.CharField(max_length=10)


class BookPrintingAction(models.Model):
    """Model is representing custom through case with additional ignored relation to same model."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE)
    chef_of_printer = models.ForeignKey(Printer, related_name='subordinates_activities', on_delete=models.CASCADE)


class ReaderProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    favourite_book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='favourite_of')
    currently_reading = models.OneToOneField(Book, on_delete=models.PROTECT, related_name='currently_read_by')

    def __str__(self):
        return '{} reader profile'.format(self.user.username)


OBSOLETE_BOOK_FIELD_CHOICES = [
    ObsoleteFieldDescription('description', models.CharField()),
    ObsoleteFieldDescription('number_of_pages', models.IntegerField()),
    ObsoleteFieldDescription('author', models.ForeignKey(Author, on_delete=models.PROTECT)),  # Note that now it is m2m
    ObsoleteFieldDescription('languages', models.ManyToManyField(Language)),  # Note that now it is FK
    ObsoleteFieldDescription('age', models.IntegerField(choices=[
        (1, 'XV'),
        (2, 'XIX'),
        (3, 'XX'),
    ])),
]


BookEditHistory = generate_history_class(  # pylint: disable=invalid-name
    Book,
    __name__,
    excluded_fields=['description'],
    obsolete_field_choices=OBSOLETE_BOOK_FIELD_CHOICES,
)
