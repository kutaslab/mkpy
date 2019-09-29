import h5py
import pytest
from tempfile import TemporaryDirectory as TMPDir
from .config import mkpy
from mkpy import h5tools


def test__get_dblock_paths__required_group_not_present():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        TEST_GROUP = "group"

        # create empty file, no groups
        h5py.File(TEST_FILE, "w").close()

        with pytest.raises(ValueError) as group_does_not_exist_err:
            h5tools.get_dblock_paths(TEST_FILE, TEST_GROUP)

        assert "does not exist" in str(group_does_not_exist_err.value)


def test__get_dblock_paths__no_dblocks():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        TEST_GROUP = "group"

        # create required data group, but no dblocks
        with h5py.File(TEST_FILE, "w") as tf:
            tf.create_group(TEST_GROUP)

        with pytest.raises(ValueError) as no_dblocks_err:
            h5tools.get_dblock_paths(TEST_FILE, TEST_GROUP)

        assert "No dblocks found" in str(no_dblocks_err.value)


def test__get_dblock_paths__disordered_dblocks():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        TEST_GROUP = "group"

        with h5py.File(TEST_FILE, "w") as tf:
            grp = tf.create_group(TEST_GROUP)
            for i in range(3):
                grp.create_dataset(f"dblock_{i}", data=())
            grp.create_dataset("dblock_4", data=())

        # now have dblock_0, dblock_1, dblock_2, dblock_4
        # dblock_3 missing
        with pytest.raises(ValueError) as disordered_dblocks_err:
            h5tools.get_dblock_paths(TEST_FILE, TEST_GROUP)

        assert "Disordered dblocks" in str(disordered_dblocks_err.value)


def test__get_dblock_paths__as_expected():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        TEST_GROUP = "group"

        with h5py.File(TEST_FILE, "w") as tf:
            grp = tf.create_group(TEST_GROUP)
            grp.create_dataset(f"dblock_1", data=())
            grp.create_dataset(f"dblock_0", data=())
            grp.create_dataset(f"dblock_2", data=())

        expected = ["group/dblock_0", "group/dblock_1", "group/dblock_2"]
        actual = h5tools.get_dblock_paths(TEST_FILE, TEST_GROUP)

        assert expected == actual


def test__get_data_group_paths__no_paths_with_dblock_0():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        BAD_GROUP = "bad"

        # create required data group, but no dblocks
        with h5py.File(TEST_FILE, "w") as tf:
            tf.create_dataset(BAD_GROUP + "/datasetA", data=())
            tf.create_dataset(BAD_GROUP + "/datasetB", data=())

        # no groups with a dblock_0, so expect an empty list
        expected = []
        actual = h5tools.get_data_group_paths(TEST_FILE)

        assert expected == actual


def test__get_data_group_paths__as_expected():

    with TMPDir() as tmpdir:

        TEST_FILE = tmpdir + "file.h5"
        GOOD_GROUP1 = "good1"
        GOOD_GROUP2 = "good2"
        BAD_GROUP1 = "bad1"
        BAD_GROUP2 = "bad2"

        # create required data group, but no dblocks
        with h5py.File(TEST_FILE, "w") as tf:

            # dlblock_0 present
            tf.create_dataset(GOOD_GROUP1 + "/dblock_0", data=())
            tf.create_dataset(GOOD_GROUP1 + "/dblock_1", data=())

            # dlblock_0 present
            tf.create_dataset(GOOD_GROUP2 + "/dblock_0", data=())

            # no dblock_0, although dblock_1 present
            tf.create_dataset(BAD_GROUP1 + "/dblock_1", data=())

            # no dblock_0, weird dataset present
            tf.create_dataset(BAD_GROUP2 + "/dataset", data=())

        # no groups with a dblock_0, so expect an empty list
        expected = [GOOD_GROUP1, GOOD_GROUP2]
        actual = h5tools.get_data_group_paths(TEST_FILE)

        assert expected == actual
