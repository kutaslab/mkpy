# mkpy is pinned to python 3.6 until other packages support 3.7

# commented out as distutils fades into oblivion
# from distutils.core import setup
# from distutils.extension import Extension
from Cython.Distutils import build_ext
from Cython.Build import cythonize
from setuptools import find_packages, setup, Extension
import numpy as np
from pathlib import Path
import re

from mkpy import get_ver

__version__ = get_ver()

# conda package version-single sourced in conda/meta.yaml {{ data.get('version') }}

extensions = [
    Extension("mkpy._mkh5", ["mkpy/_mkh5.pyx"], include_dirs=[np.get_include()])
]

setup(
    name="mkpy",
    version=__version__,
    description="kutaslab eeg data utilities",
    author="Thomas P. Urbach, Andrey Portnoy, forked from Nathaniel Smith",
    author_email="turbach@ucsd.edu",
    url="http://kutaslab.ucsd.edu/people/urbach",
    packages=find_packages(exclude=["tests"]),  # ['mkh5.core', 'mkh5.utils'],
    scripts=["bin/pygarv"],
    cmdclass={"build_ext": build_ext},
    ext_modules=cythonize(extensions),
)
