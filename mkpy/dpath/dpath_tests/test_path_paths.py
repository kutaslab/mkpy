import nose
from nose.tools import raises

# import dpath.path
# import dpath.exceptions
# import dpath.options

import mkpy.dpath.exceptions
import mkpy.dpath.path
import mkpy.dpath.options


@raises(mkpy.dpath.exceptions.InvalidKeyName)
def test_path_paths_empty_key_disallowed():
    tdict = {"Empty": {"": {"Key": ""}}}
    for x in mkpy.dpath.path.paths(tdict):
        pass


def test_path_paths_empty_key_allowed():
    tdict = {"Empty": {"": {"Key": ""}}}
    parts = []
    mkpy.dpath.options.ALLOW_EMPTY_STRING_KEYS = True
    for x in mkpy.dpath.path.paths(tdict, dirs=False, leaves=True):
        path = x
    for x in path[:-1]:
        parts.append(x[0])
    mkpy.dpath.options.ALLOW_EMPTY_STRING_KEYS = False
    assert "/".join(parts) == "Empty//Key"


def test_path_paths_int_keys():
    mkpy.dpath.path.validate(
        [
            ["I", dict],
            ["am", dict],
            ["path", dict],
            [0, dict],
            ["of", dict],
            [2, int],
        ]
    )
