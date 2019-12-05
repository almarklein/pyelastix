""" PyElastix setup script

Steps to do a new release:

Preparations:
  * Test on Windows, Linux, Mac
  * Make release notes
  * Update API documentation and other docs that need updating

Bump the version:
  * update __version__
  * Tag the tip changeset as version x.x

Register and upload package
  * python setup.py register
  * python setup.py sdist upload
  * update conda-forge feedstock

"""

import os
from distutils.core import setup

name = 'pyelastix'
description = 'Python wrapper for the Elastix nonrigid registration toolkit'

# Get version and docstring
__version__ = None
__doc__ = ''
docStatus = 0 # Not started, in progress, done
initFile = os.path.join(os.path.dirname(__file__), 'pyelastix.py')
for line in open(initFile).readlines():
    if (line.startswith('__version__')):
        exec(line.strip())
    elif line.startswith('"""'):
        if docStatus == 0:
            docStatus = 1
            line = line.lstrip('"')
        elif docStatus == 1:
            docStatus = 2
    if docStatus == 1:
        __doc__ += line



setup(
    name = name,
    version = __version__,
    author = 'Almar Klein',
    author_email = 'almar.klein@gmail.com',
    license = 'MIT',

    url = 'https://github.com/almarklein/pyelastix',
    keywords = "image registration, deformation, nonrigid, elastic, elastix",
    description = description,
    long_description = __doc__,

    platforms = 'any',
    provides = ['pyelastix'],

    py_modules = ['pyelastix'],

    classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Science/Research',
          'Intended Audience :: Education',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Operating System :: Unix',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          ],
    )
