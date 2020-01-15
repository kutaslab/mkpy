from pathlib import Path
import mkpy
from mkpy import get_ver


def test_get_ver():
    # screen version for updates
    get_ver()
