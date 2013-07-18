import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='bakthat',
    version='0.7.0',
    author='Thomas Sileo',
    author_email='thomas.sileo@gmail.com',
    description='',
    license='MIT',
    keywords='aws s3 glacier backup restore archive',
    url='http://docs.bakthat.io',
    packages=find_packages(exclude=['ez_setup', 'tests', 'tests.*']),
    long_description=read('README.rst'),
    install_requires=['boto', 'peewee', 'pyyaml'],
    test_suite="tests",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Archiving :: Backup",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    zip_safe=False,
)
