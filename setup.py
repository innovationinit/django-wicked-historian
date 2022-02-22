# -*- coding: utf-8 -*-
import os
from setuptools import find_packages, setup


with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-wicked-historian',
    version='1.0.0',
    description='A complete solution for creating automatic history of Django models.',
    long_description=README,
    long_description_content_type='text/markdown',
    author='IIIT',
    author_email='github@iiit.pl',
    packages=find_packages(exclude=[
        'testproject',
        'testproject.*',
    ]),
    include_package_data=True,
    install_requires=[
        'Django>=2.1,<3.0',
        'django-diffable>=1.0.0'
    ],
    extras_require={
        'mysql': ['django-mysql>=2.2.0'],
        'postgres': ['psycopg2>=2.6.2'],
        'django-jsonfield': ['django-jsonfield>=1.0.1'],
    },
    tests_require=[
        'freezegun>=0.3.10',
        'django-jsonfield>=1.0.1',
        'pytz>=2018.3',
        'factory_boy==2.10.0',
        'django-override-storage>=0.1.2',
    ],
    test_suite='testproject.runtests.run_tests',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.10',
    ],
)
