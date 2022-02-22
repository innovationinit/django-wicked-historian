from django.test.testcases import TestCase

from wicked_historian.handlers import (
    _prepare_sql_view_code_from_rows,
    _prepare_view_rows_from_models,
    ViewRow,
)


class WickedHistorianViewCreationTestCase(TestCase):

    def test_row_creation_from_models(self):
        expected_rows = [
            ViewRow(db_table='testapp_bookedithistory', field_id='1664f478eaaf650ea5dbeaf42b28608e47fc9b2e', field_name='id'),
            ViewRow(db_table='testapp_bookedithistory', field_id='060fd0b449aa0197cb3ea60b3d0c168c9ba82907', field_name='title'),
            ViewRow(db_table='testapp_bookedithistory', field_id='61ca3c8176da7acfe917bbe784bec8f605de0d4a', field_name='description'),
            ViewRow(db_table='testapp_bookedithistory', field_id='ce06ba6406ec1d70dbf49d249ce8456c574b076c', field_name='issue_year'),
            ViewRow(db_table='testapp_bookedithistory', field_id='5c9b3e1e7bdddf3ad10737d47ab592063ca49542', field_name='language'),
            ViewRow(db_table='testapp_bookedithistory', field_id='a0b181aa0245ba6b1431728c69c1b6e731681293', field_name='has_pictures'),
            ViewRow(db_table='testapp_bookedithistory', field_id='450590934e07680f5de606e782733a9b15cd8c0b', field_name='date_of_publication'),
            ViewRow(db_table='testapp_bookedithistory', field_id='e67f1c219d2da439e7e69ec4fd005257c7c8e6bc', field_name='moment_of_appearance_on_torrents'),
            ViewRow(db_table='testapp_bookedithistory', field_id='f9ee7df21e32f884d6e96f03c7976140e8daa60f', field_name='ebook_length'),
            ViewRow(db_table='testapp_bookedithistory', field_id='4156cdd39b37e020d99336a32ba7d236b705a78d', field_name='text_as_pdf'),
            ViewRow(db_table='testapp_bookedithistory', field_id='b5402cbba33e2af751a818d323f6bea8d98dc41f', field_name='literary_period'),
            ViewRow(db_table='testapp_bookedithistory', field_id='35d347903f996e9efd71a2bfd97e627edd05c2c1', field_name='issue_number'),
            ViewRow(db_table='testapp_bookedithistory', field_id='b6bf059d6b5e803ffd5dd75307c01bcdabfa96b2', field_name='number_of_downloads_on_torrents'),
            ViewRow(db_table='testapp_bookedithistory', field_id='90a0792c407b45517adab1433eee19e24c24fcf3', field_name='encrypted_book'),
            ViewRow(db_table='testapp_bookedithistory', field_id='57337229b0bd5d6fed0e979dfaeb9e58a61a12f9', field_name='cash_lost_because_of_piracy'),
            ViewRow(db_table='testapp_bookedithistory', field_id='cbf34af4615b07c850b0804e4f8ede8abb882312', field_name='plain_text'),
            ViewRow(db_table='testapp_bookedithistory', field_id='62a3bb688399f104f058bf3ba1e608696f3c9438', field_name='first_download_hour'),
            ViewRow(db_table='testapp_bookedithistory', field_id='0b92a0cfb0e68cec7199c16eb2fb5b016b54aaf6', field_name='book_shelf_slot'),
            ViewRow(db_table='testapp_bookedithistory', field_id='9f06438fcf5e2f6c1b4dfcd0f0fd2383582708c2', field_name='authors'),
            ViewRow(db_table='testapp_bookedithistory', field_id='79bdd035bd81ced2bd949c47a3d34deb83d8d9f3', field_name='pirates'),
            ViewRow(db_table='testapp_bookedithistory', field_id='677ce91117438c0a85f0727f7370c42bb13a114b', field_name='printers'),
            ViewRow(db_table='testapp_bookedithistory', field_id='075b2280fe1189a53dbe62549ff6bc2afa4a8cba', field_name='chapter_set'),
            ViewRow(db_table='testapp_bookedithistory', field_id='75f58cbab5da59e2a6fcf39316b7be041218e0be', field_name='description'),
            ViewRow(db_table='testapp_bookedithistory', field_id='4ed887478379df8829a66f0b8d6336308f920534', field_name='number_of_pages'),
            ViewRow(db_table='testapp_bookedithistory', field_id='6210813f2dd749a2de24134587b2830e8ba83833', field_name='author'),
            ViewRow(db_table='testapp_bookedithistory', field_id='6a1c79e5fa38318e6f315487c1556a6680d02f9f', field_name='languages'),
            ViewRow(db_table='testapp_bookedithistory', field_id='6dca6b75c546bff58cbd44e298a457cdcdec62ca', field_name='age'),
        ]

        rows = _prepare_view_rows_from_models()
        self.assertListEqual(rows, expected_rows)

    def test_sql_view_code_creation_from_rows(self):
        rows = [
            ViewRow(db_table='testapp_author', field_id='c85320d9ddb90c13f4a215f1f0a87b531ab33310', field_name='id'),
            ViewRow(db_table='testapp_author', field_id='c71de136f9377eca14b4218cc7001c8060c6974f', field_name='name'),
        ]

        expected_sql = 'CREATE OR REPLACE VIEW wicked_historian_managed_fields (db_table, field_id, field_name) AS ' \
                       'SELECT %s, %s, %s UNION SELECT %s, %s, %s'
        expected_values = ['testapp_author', 'c85320d9ddb90c13f4a215f1f0a87b531ab33310', 'id',
                           'testapp_author', 'c71de136f9377eca14b4218cc7001c8060c6974f', 'name']

        sql, values = _prepare_sql_view_code_from_rows(rows)
        self.assertEqual(sql, expected_sql)
        self.assertListEqual(values, expected_values)
