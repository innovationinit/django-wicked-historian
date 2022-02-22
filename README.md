Django Wicked Historian
=======================

![example workflow](https://github.com/innovationinit/django-wicked-historian/actions/workflows/test-package.yml/badge.svg?branch=main)
[![Coverage Status](https://coveralls.io/repos/github/innovationinit/django-wicked-historian/badge.svg)](https://coveralls.io/github/innovationinit/django-wicked-historian)


A complete solution for creating automatic history of Django models.

## Installation

Package can be installed using PyPi:

```
$ pip install django-wicked-historian
```

You can also use extras to ensure some additional dependencies specific for implementation of JSONField which is required for this package to work properly.

```
$ pip install django-wicked-historian[mysql]
$ pip install django-wicked-historian[postgres]
$ pip install django-wicked-historian[django-jsonfield]
```


## Defining JSONField to be used

Package requires some configuration. You need to specify JSONField implementation which package gonna use to store values of model fields in your settings:

```
from wicked_historian.encoder import JSONEncoder

WICKED_HISTORIAN_JSON_FIELD_CLASS = 'path.to.JSONField'
WICKED_HISTORIAN_JSON_FIELD_KWARGS = {
    'encoder': JSONEncoder,
}
```

`WICKED_HISTORIAN_JSON_FIELD_CLASS` - path to JSON field class to be used
`WICKED_HISTORIAN_JSON_FIELD_KWARGS` - kwargs used for instantiate of supplied class

Remember to always use `wicked_historian.encoder.JSONEncoder` as an encoder for this field.

### Example configuration for common used fields

#### jsonfield.JSONField

```
WICKED_HISTORIAN_JSON_FIELD_CLASS = 'jsonfield.JSONField'
WICKED_HISTORIAN_JSON_FIELD_KWARGS = {
    'encoder_class': JSONEncoder,
}
```

#### django.contrib.postgres.fields.JSONField

For Django >= 2.1 use builtin field with our encoder.

```
WICKED_HISTORIAN_JSON_FIELD_CLASS = 'django.contrib.postgres.fields.JSONField'
WICKED_HISTORIAN_JSON_FIELD_KWARGS = {
    'encoder': JSONEncoder,
}
```

#### django_mysql.models.fields.JSONField

This field in version 2.2.0 of django-mysql package doesn't support supplying custom json encoder. However this package supplies subclass of this field with support of custom encoders and `wicked_historian.encoder.JSONEncoder` is default encoder.

Use field `wicked_historian.compat.mysql.JSONField` instead:

```
WICKED_HISTORIAN_JSON_FIELD_CLASS = 'wicked_historian.compat.mysql.JSONField'
WICKED_HISTORIAN_JSON_FIELD_KWARGS = {}
```


## Adding history to model of choice

Model for which history is going to be generated should inherit from `wicked_historian.models.DiffableHistoryModel` and have a class for history entries specified in the Model.Meta class. History class should be created using factory `wicked_historian.utils.generate_history_class`:

```
from wicked_historian.models import DiffableHistoryModel
from wicked_historian.utils import generate_history_class


class Book(DiffableHistoryModel):
    title = models.CharField(max_length=100)

    class Meta:
        history_class = 'this_app.models.BookEditHistory'


BookEditHistory = generate_history_class(Book, __name__)
```

If there is a need for customizing the history model, it can be generated with the `abstract` option and used as a base model for a custom history model.

```
class BookEditHistory(generate_history_class(Book, __name__, abstract=True)):
    custom_field = models.IntegerField(default=0)

    def custom_method(self):
        return self.custom_field + 10
```

### Changes in model's fields set

If the set of model fields changes in a non-incremental way (fields were removed or changed their type), old definitions of such fields should be supplied to the `generate_history_class` factory for handling already existing history entries concerning these fields:

```
from wicked_historian.utils import ObsoleteFieldDescription

BookEditHistory = generate_history_class(
    Book,
    __name__,
    obsolete_field_choices=[
        ObsoleteFieldDescription('title', models.TextField()),
        ObsoleteFieldDescription('number_of_pages', models.IntegerField()),
        ObsoleteFieldDescription('age', models.IntegerField(choices=[
            (1, 'XV'),
            (2, 'XIX'),
            (3, 'XX'),
        ])),
    ],
)
```


### Excluding fields from history

If there is no need for generating history for some fields, they can be excluded by supplying list of unwanted fields name to `generate_history_class`. History for these will not be generated, but any already existing history can be read.

```
from wicked_historian.utils import ObsoleteFieldDescription

BookEditHistory = generate_history_class(
    Book,
    __name__,
    excluded_fields=['title'],
)
```

### Choices in model fields

Please note that when the set of choices in model fields changes in a non-incremental way, some values may be impossible to restore from history entries. That's why you should always have a superset of all choices ever used in this fields declared in the field.

## Reading/accessing history

Instance history should be accessed by history model.

### Retrieving whole history

To retrieve whole history use method `get_for`, e.g. `BookEditHistory.get_for(book)` will return list of whole `Book` instance history as dicts.

### Filtering and searching history

To filter history use history model manager (e.g. `BookEditHistory.objects.filter(user=some_user, model=book)`) and transform history entry to dict form using `get_entry_for` method.

```
history_entry_instances = BookEditHistory.objects.filter(user=some_user, model=book)
history_entries = BookEditHistory.get_history_entry(history_entry_instance) for history_entry_instance in history_entry_instances
```

### Troubleshooting custom m2m handling

When there is risk of sending by Django both signals model related (pre_save, post_delete etc.) and m2m related use `wicked_historian.signals_exclusion.signal_exclusion` and make those changes in `signal_exclusion.model_signals_exclusion_context` context. When in context calling `signal_exclusion.are_model_signals_excluded` with the same arguments context was created returns `True`.


## License
The Django Wicked Historian package is licensed under the [FreeBSD
License](https://opensource.org/licenses/BSD-2-Clause).
