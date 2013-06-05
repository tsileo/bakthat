import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="bakthat",
    version="0.6.0",
    author="Thomas Sileo",
    author_email="thomas.sileo@gmail.com",
    description="Bakthat is a MIT licensed backup framework written in Python, it's both a command line tool and a Python module that helps you manage backups on Amazon S3/Glacier and OpenStack Swift. It automatically compress, encrypt (symmetric encryption) and upload your files.",
    license="MIT",
    keywords="aws s3 glacier backup restore archive",
    url="http://docs.bakthat.io",
    packages=find_packages(exclude=['ez_setup', 'tests', 'tests.*']),
    long_description=read('README.rst'),
    install_requires=["aaargh", "boto", "pycrypto", "beefish", "grandfatherson", "peewee", "byteformat", "pyyaml", "sh", "requests", "events"],
    entry_points={'console_scripts': ["bakthat = bakthat:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Archiving :: Backup",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    zip_safe=False,
)
