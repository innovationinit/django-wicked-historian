from datetime import datetime

import pytz
from freezegun import freeze_time

from django.test import TestCase


class FreezeTimeTestCase(TestCase):
    frozen_time = datetime(2005, 4, 2, 19, 37, tzinfo=pytz.UTC)

    def setUp(self):  # pylint: disable=invalid-name
        super().setUp()
        freezer = freeze_time(self.frozen_time)
        freezer.start()
        self.addCleanup(freezer.stop)
