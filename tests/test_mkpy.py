from pathlib import Path
import mkpy
from mkpy import get_ver


def test_mkpy__init__version():
    # screen version for updates
    assert mkpy.__version__ == "0.1.6"


def test_mkpy__init__getver():
    # smoke test
    __version__ = get_ver()
