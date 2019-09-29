# mkpy is restricted to python 3.6 until other packages support 3.7
#
# To install mkpy in an existing python 3.6 conda environment at the
# terminal command line, cd to where this setup.py and
# requirements.txt are found. Then run
#
#  conda activate my_env
#  pip install -r requirements.txt
#  pip install .
#
# To create a python 3.6 conda environment from scratch, run this with a
# sensible name in place of "some_env"
#
#   > create conda -n some_env python=3.6 pip
#
# Changes for Fall 2017
#  - distutils stuff stopped working for Cython, switched to setup tools
#
# to install in development mode with an egg from this directory run
#
#     python ./setup.py build_ext --inplace
#     python ./setup.py develop -d ~/.local/lib/python3.6/site-packages/
#
#  to install stable package to default python site-packages as root
#
#    pip install .
#
# http://python-packaging.readthedocs.io/en/latest/minimal.html

# commented out as distutils fades into oblivion
# from distutils.core import setup
# from distutils.extension import Extension
from Cython.Distutils import build_ext
from Cython.Build import cythonize
from setuptools import find_packages, setup, Extension
import numpy as np

from mkpy.__version__ import __version__

extensions = [
    Extension(
        "mkpy._mkh5", ["mkpy/_mkh5.pyx"], include_dirs=[np.get_include()]
    )
]

setup(
    name="mkpy",
    version=__version__,
    description="kutaslab eeg data utilities",
    author="Thomas P. Urbach, Andrey Portnoy, forked from Nathaniel Smith",
    author_email="turbach@ucsd.edu",
    url="http://kutaslab.ucsd.edu/people/urbach",
    packages=find_packages(),  # ['mkh5.core', 'mkh5.utils'],
    scripts=["bin/pygarv"],
    cmdclass={"build_ext": build_ext},
    ext_modules=cythonize(extensions),
)
