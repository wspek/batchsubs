"""
 Created by waldo on 3/17/17
"""

from setuptools import setup, find_packages

__author__ = "waldo"
__project__ = "batchsubs"

setup(name='batchsubs',
      version='0.1.0',
      description='Download subtitles in batch from OpenSubtitles.org.',
      url='https://gitlab.com/wspek/batchsubs',
      author='Waldo Spek',
      author_email='waldospek@gmail.com',
      keywords='subtitle opensubtitle imdb download batch',
      packages=find_packages(),
      zip_safe=False)
