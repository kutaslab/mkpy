import nose
from nose.tools import assert_raises
import mkpy.dpath as dpath

try:
    # python3, especially 3.8
    from collections.abc import MutableSequence
    from collections.abc import MutableMapping
except ImportError:
    # python2
    from collections import MutableSequence
    from collections import MutableMapping


class TstMapping(MutableMapping):
    def __init__(self, data={}):
        self._mapping = {}
        self._mapping.update(data)

    def __len__(self):
        return len(self._mapping)

    def __iter__(self):
        return iter(self._mapping)

    def __contains__(self, key):
        return key in self._mapping

    def __getitem__(self, key):
        return self._mapping[key]

    def __setitem__(self, key, value):
        self._mapping[key] = value

    def __delitem__(self, key):
        del self._mapping[key]


class TstSequence(MutableSequence):
    def __init__(self, data=list()):
        self._list = data

    def __len__(self):
        return len(self._list)

    def __getitem__(self, idx):
        return self._list[idx]

    def __delitem__(self, idx):
        del self._list[key]

    def __setitem__(self, idx, value):
        self._list[idx] = value

    def __str__(self):
        return str(self._list)

    def __eq__(self, other):
        return self._list == other._list

    def __ne__(self, other):
        return not self.__eq__(other)

    def insert(self, idx, value):
        self._list.insert(idx, value)

    def append(self, value):
        self.insert(len(self._list), value)


def test_types_set():
    data = TstMapping({"a": TstSequence([0])})

    dpath.util.set(data, "/a/0", 1)
    assert data["a"][0] == 1
    data["a"][0] = 0
    dpath.util.set(data, ["a", "0"], 1)
    assert data["a"][0] == 1


def test_types_get_list_of_dicts():
    tdict = TstMapping({"a": TstMapping({"b": TstSequence([{0: 0}, {0: 1}, {0: 2}])})})
    res = dpath.path.get(
        tdict, dpath.path.path_types(tdict, ["a", "b", 0, 0]), view=True
    )
    assert isinstance(res["a"]["b"], TstSequence)
    assert len(res["a"]["b"]) == 1
    assert res["a"]["b"][0][0] == 0


def test_types_merge_simple_list_replace():
    src = TstMapping({"list": TstSequence([7, 8, 9, 10])})
    dst = TstMapping({"list": TstSequence([0, 1, 2, 3])})
    dpath.util.merge(dst, src, flags=dpath.util.MERGE_REPLACE)
    nose.tools.eq_(dst["list"], TstSequence([7, 8, 9, 10]))


def test_types_get_absent():
    ehash = TstMapping()
    assert_raises(KeyError, dpath.util.get, ehash, "/a/b/c/d/f")
    assert_raises(KeyError, dpath.util.get, ehash, ["a", "b", "c", "d", "f"])


def test_types_get_glob_multiple():
    ehash = TstMapping(
        {
            "a": TstMapping(
                {
                    "b": TstMapping(
                        {"c": TstMapping({"d": 0}), "e": TstMapping({"d": 0})}
                    )
                }
            )
        }
    )
    assert_raises(ValueError, dpath.util.get, ehash, "/a/b/*/d")
    assert_raises(ValueError, dpath.util.get, ehash, ["a", "b", "*", "d"])


def test_delete_filter():
    def afilter(x):
        if int(x) == 31:
            return True
        return False

    data = TstMapping({"a": TstMapping({"b": 0, "c": 1, "d": 31})})
    dpath.util.delete(data, "/a/*", afilter=afilter)
    assert data["a"]["b"] == 0
    assert data["a"]["c"] == 1
    assert "d" not in data["a"]
