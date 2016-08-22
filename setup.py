#!/usr/bin/env python

# -----------------------------------------------------------------------------
# Copyright (c) 2013, The Deblur Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from setuptools import setup
from glob import glob


__version__ = "0.0.1-dev"


classes = """
    Development Status :: 2 - Pre-Alpha
    License :: OSI Approved :: BSD License
    Topic :: Scientific/Engineering :: Bio-Informatics
    Topic :: Software Development :: Libraries :: Application Frameworks
    Topic :: Software Development :: Libraries :: Python Modules
    Programming Language :: Python
    Programming Language :: Python :: 3.5
    Programming Language :: Python :: Implementation :: CPython
    Operating System :: POSIX :: Linux
    Operating System :: MacOS :: MacOS X
"""

long_description = ("Deblur: a greedy deconvolution algorithm based on known "
                    "read error profiles")

classifiers = [s.strip() for s in classes.split('\n') if s]

setup(name='deblur',
      version=__version__,
      long_description=long_description,
      license="BSD",
      description='Deblur',
      author="Deblur development team",
      author_email="amnonim@gmail.com",
      url='https://github.com/biocore/deblur',
      test_suite='nose.collector',
      packages=['deblur'],
      package_data={},
      scripts=glob('scripts/*'),
      extras_require={'test': ["nose >= 0.10.1", "pep8"],
                      'doc': ["Sphinx >= 1.2.2", "sphinx-bootstrap-theme"]},
      install_requires=['click >= 6', 'numpy >= 1.7',
                        'scikit-bio >= 0.2.2, < 0.3.0',
                        'biom-format >= 2.1.3, < 2.2.0',
                        'h5py >= 2.2.0'],
      classifiers=classifiers
      )
