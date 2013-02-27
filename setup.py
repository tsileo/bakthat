import os
import sys
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "bakthat",
    version = "0.3.10",
    author = "Thomas Sileo",
    author_email = "thomas.sileo@gmail.com",
    description = "Compress, encrypt (symmetric encryption) and upload files directly to Amazon S3/Glacier in a single command. Can also be used as a python module.",
    license = "MIT",
    keywords = "aws s3 glacier backup restore archive",
    url = "https://github.com/tsileo/bakthat",
    packages=find_packages(exclude=['ez_setup', 'tests', 'tests.*']),
    long_description= read('README.rst'),
    install_requires=[
        "aaargh", "boto", "pycrypto", "beefish", "grandfatherson"
        ],
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