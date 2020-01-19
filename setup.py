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

# enforce conda meta.yaml semantic version == package __init__
jinja_version = f'{{% set version = "{__version__}" %}}'
meta_yaml_f = "./conda/meta.yaml"
with open(meta_yaml_f) as f:
    conda_ver = re.match(r"^" + jinja_version, f.read())
    if not conda_ver:
        fail_msg = (
            "conda/meta.yaml must start with a jinja variable line exactly"
            f"like this: {jinja_version}"
        )
        raise Exception(fail_msg)

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
    packages=find_packages(exclude=["tests"]),  # ['mkh5.core', 'mkh5.utils'],
    scripts=["bin/pygarv"],
    cmdclass={"build_ext": build_ext},
    ext_modules=cythonize(extensions),
)
