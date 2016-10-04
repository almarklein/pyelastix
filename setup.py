""" Steps to do a new release:

Preparations:
  * Test on Windows, Linux, Mac
  * Test on a machine with OpenGl v1.1 (e.g. winXP virtual machine)
  * Make release notes
  * Update API documentation and other docs that need updating.

Test installation:
  * clear the build and dist dir (if they exist)
  * python setup.py register -r http://testpypi.python.org/pypi
  * python setup.py sdist upload -r http://testpypi.python.org/pypi 
  * pip install -i http://testpypi.python.org/pypi

Define the version:
  * update __version__ in __init__.py
  * Tag the tip changeset as version x.x

Generate and upload package (preferably on Windows)
  * python setup.py register
  * python setup.py sdist upload

Announcing:
  * It can be worth waiting a day for eager users to report critical bugs
  * Announce in scipy-user, visvis mailing list, G+
  
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
    keywords = "image registration deformation nonrigid elastic elastix",
    description = description,
    long_description = __doc__,
    
    platforms = 'any',
    provides = ['pyelastix'],
    
    py_modules = ['pyelastix'],
    package_dir = {'visvis': '.'},
    
    classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Science/Research',
          'Intended Audience :: Education',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          ],
    )
