import re
from pathlib import Path
import mkpy
from mkpy import get_ver


def test_mkpy__init__getver():
    # smoke test
    __version__ = get_ver()
