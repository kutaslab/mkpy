import os
from pathlib import Path
from copy import deepcopy
import pytest
import numpy as np
import pandas as pd
import requests  # URL IO
from mkpy import dpath  # local fork of dpath

import mne
from .config import TEST_DIR

import mkpy.mkh5 as mkh5
from mkpy.io import mkh5mne
from mkpy.io.mkh5mne import RawMkh5

DATA_DIR = TEST_DIR("data")  # Path(".")
DATA_DIR.mkdir(parents=True, exist_ok=True)

TEST_APPARATUS_YAML = str(DATA_DIR / "mne_32chan_apparatus.yml")

# ------------------------------------------------------------
# CI needs to download the big mkh5 .h5 files, usually skip for local testing
# Zenodo version 0.0.4 for mkpy 0.2.4
TEST_DATA_URL = r"https://zenodo.org/record/4099632/files/"
ZENODO_RAW_F = "sub000eeg.h5"
ZENODO_EPOCHS_F = "sub000p3.h5"
for filename in [ZENODO_RAW_F, ZENODO_EPOCHS_F]:
    if "GITHUB_ACTIONS" in os.environ.keys():
        print(f"downloading {DATA_DIR / filename} from {TEST_DATA_URL} ... please wait")
        resp = requests.get(TEST_DATA_URL + str(filename))
        with open(DATA_DIR / filename, "wb") as _fd:
            _fd.write(resp.content)
            h5 = mkh5.mkh5(DATA_DIR / filename)
            h5.data_blocks

TEST_RAW_MKH5_FILE = DATA_DIR / ZENODO_RAW_F
TEST_EPOCHS_MKH5_FILE = DATA_DIR / ZENODO_EPOCHS_F
assert TEST_RAW_MKH5_FILE.exists()
assert TEST_EPOCHS_MKH5_FILE.exists()


# legal garv annotation intervals for TEST_EPOCHS_MKH5_FILE
GARV_ANNOTATIONS_MS = dict(
    event_channel="log_evcodes", tmin=-500, tmax=500, units="ms"
)

GARV_ANNOTATIONS_S = dict(
    event_channel="log_evcodes", tmin=-0.5, tmax=0.5, units="s"
)

# bad interval
GARV_ANNOTATIONS_BAD = dict(
    event_channel="log_evcodes", tmin=500, tmax=-500, units="ms"
)

# ------------------------------------------------------------
# Backend and QC checks


def test__check_api_params_raw():
    """RawMkh5 keyword parameters"""

    # mkh5 file arg
    with pytest.raises(TypeError):
        mkh5mne._check_api_params()

    with pytest.raises(TypeError):
        mkh5mne._check_api_params(RawMkh5)

    with pytest.raises(mkh5mne.Mkh5FileAccessError):
        mkh5mne._check_api_params(RawMkh5, "no_such.h5")

    # ------------------------------------------------------------
    # fail on unknown kwarg
    with pytest.raises(ValueError):
        mkh5mne._check_api_params(RawMkh5, TEST_RAW_MKH5_FILE, not_a_kw="arg")

    # dblock paths
    mkh5mne._check_api_params(
        RawMkh5, TEST_RAW_MKH5_FILE, dblock_paths=["open/dblock_0"]
    )

    for fail, param in [
        (AssertionError, None),
        (TypeError, "not_a_list"),
        (TypeError, [1, 2, 3]),  # not a list of str
        # (mkh5mne.Mkh5DblockPathError, ["no_such_dblock_path"]),
    ]:
        with pytest.raises(fail):
            mkh5mne._check_api_params(RawMkh5, TEST_RAW_MKH5_FILE, dblock_paths=param)

    # these should pass
    for garv_anns in [GARV_ANNOTATIONS_MS, GARV_ANNOTATIONS_S]:
        mkh5mne._check_api_params(
            RawMkh5,
            TEST_EPOCHS_MKH5_FILE,
            dblock_paths=["sub000/dblock_0"],
            garv_annotations=garv_anns
        )

    # these should fail
    for exc, kws in [
            (TypeError, None),
            (KeyError, "missing_key"),
            (KeyError, {"extra_key": "val"}),
            (ValueError, {"units": "seconds"}),
            (ValueError, {"tmin": 4, "tmax": 4}),
            (ValueError, {"tmin": 4, "tmax": 3}),
    ]:
        with pytest.raises(exc):
            if kws is None:
                garv_anns = ["not", "a", "dict"]  # wrong type
            else:
                # pollute a legal garv annotation
                garv_anns = GARV_ANNOTATIONS_MS.copy()

                if kws == "missing_key":
                    del(garv_anns["event_channel"])
                else:
                    garv_anns.update(kws)

            mkh5mne._check_api_params(
                RawMkh5,
                TEST_EPOCHS_MKH5_FILE,
                dblock_paths=["sub000/dblock_0"],
                garv_annotations=garv_anns
            )

    # smoke test RawMkh5, EpochsMkh5 w/  yaml file  go, no-go
    mkh5mne._check_api_params(
        RawMkh5,
        TEST_RAW_MKH5_FILE,
        dblock_paths=["open/dblock_0"],
        apparatus_yaml=TEST_APPARATUS_YAML,
    )
    with pytest.raises(mkh5mne.ApparatusYamlFileError):
        mkh5mne._check_api_params(
            RawMkh5,
            TEST_RAW_MKH5_FILE,
            dblock_paths=["open/dblock_0"],
            apparatus_yaml=TEST_APPARATUS_YAML + "X",
        )

    # ignore_keys param go, no-go
    mkh5mne._check_api_params(
        RawMkh5,
        TEST_RAW_MKH5_FILE,
        dblock_paths=["open/dblock_0"],
        ignore_keys=["subject_info", "meas_id"],
    )
    for bad_ignore_keys in [(1, 2), ["meas_id", 3.5]]:
        with pytest.raises(ValueError):
            mkh5mne._check_api_params(
                RawMkh5,
                TEST_RAW_MKH5_FILE,
                dblock_paths=["open/dblock_0"],
                ignore_keys=bad_ignore_keys,
            )


@pytest.mark.parametrize("key", ["fail_on_info", "fail_on_montage"])
@pytest.mark.parametrize("val", [True, False])
def test__check_api_params_fail_on_info_montage(key, val):

    # smoke test RawMkh5, EpochsMkh5 w/  yaml file
    mkh5mne._check_api_params(
        RawMkh5, TEST_RAW_MKH5_FILE, dblock_paths=["open/dblock_0"], **{key: val}
    )

    val = "X"
    with pytest.raises(TypeError):
        mkh5mne._check_api_params(
            RawMkh5, TEST_RAW_MKH5_FILE, dblock_paths=["open/dblock_0"], **{key: val}
        )


@pytest.mark.parametrize(
    "verb_level",
    [
        "info",
        "quiet",
        "debug",
        pytest.param(
            "not_a_level", marks=pytest.mark.xfail(strict=True, reason=ValueError)
        ),
        pytest.param(None, marks=pytest.mark.xfail(strict=True, reason=ValueError)),
    ],
)
@pytest.mark.parametrize(
    "_class, _test_file, _class_kwargs",
    [
        (RawMkh5, TEST_RAW_MKH5_FILE, None),
        # (EpochsMkh5, TEST_EPOCHS_MKH5_FILE, {"epochs_name": "ms100"})
    ],
)
def test__check_api_params_verbose(_class, _test_file, _class_kwargs, verb_level):

    kwargs = {}
    if _class_kwargs:
        kwargs.update(_class_kwargs)
    kwargs.update({"verbose": verb_level})
    mkh5mne._check_api_params(
        _class, _test_file, dblock_paths=["open/dblock_0"], **kwargs
    )


def test__validate_hdr_for_mne():
    # ommitted keys should xfail with Mkh5HeaderKeyError
    # wrong values should xfail with Mkh5HeaderValueError
    # TODO: wrong types should xfail with Mkh5HeaderTypeError
    hdr_mne_test_key_vals = [
        # key errors
        ("apparatus", None),
        ("apparatus/streams", None),
        ("apparatus/sensors", None),
        ("apparatus/fiducials", None),
        ("apparatus/common_ref", None),
        ("apparatus/space", None),
        ("apparatus/space/coordinates", None),
        ("apparatus/space/distance_unit", None),
        ("apparatus/space/orientation", None),
        ("apparatus/streams/lle/mne_type", None),
        ("apparatus/streams/lle/pos", None),
        ("apparatus/sensors/lle/x", None),
        ("apparatus/fiducials/lpa", None),
        ("apparatus/fiducials/rpa", None),
        ("apparatus/fiducials/nasion", None),
        # key: value errors
        ("h5_dataset", "not_a/dblock_X"),
        ("samplerate", "X"),
        ("apparatus/space/coordinates", "X"),
        ("apparatus/space/distance_unit", "X"),
        ("apparatus/space/orientation", "X"),
        ("apparatus/common_ref", "X"),
        ("apparatus/streams/lle/mne_type", "ege"),
        ("apparatus/streams/lle/pos", "MiPA"),
        ("apparatus/streams/lle/neg", "MiPA"),
        ("apparatus/sensors/lle/x", "X"),
        ("apparatus/fiducials/lpa/x", "X"),
        ("apparatus/fiducials/rpa/x", "X"),
        ("apparatus/fiducials/nasion/x", "X"),
    ]

    # mkh5 = mkh5mne.RawMkh5(TEST_RAW_MKH5_FILE).mkh5
    h5 = mkh5.mkh5(TEST_RAW_MKH5_FILE)
    for dblock_path in [h5.dblock_paths[0]]:
        hdr, _ = h5.get_dblock(dblock_path)
        mkh5mne._validate_hdr_for_mne(hdr)

    # tests on last header from the for-loop
    for test_key, test_val in hdr_mne_test_key_vals:
        if test_val is None:
            print(f"testing key={test_key} exists")
            # clobber required key
            hdr_copy = deepcopy(hdr)
            dpath.util.delete(hdr_copy, test_key)
            with pytest.raises(mkh5mne.Mkh5HeaderKeyError) as err_info:
                mkh5mne._validate_hdr_for_mne(hdr_copy)
            print(f"xfailed as {err_info.typename}: {err_info.value}")

        else:
            print(f"testing key={test_key}: value={test_val}")
            hdr_copy = deepcopy(hdr)
            # set bad value
            dpath.util.set(hdr_copy, test_key, test_val)
            with pytest.raises(mkh5mne.Mkh5HeaderValueError) as err_info:
                mkh5mne._validate_hdr_for_mne(hdr_copy)
            print(f"xfailed as {err_info.typename}: {err_info.value}")


def test__parse_hdr_for_mne():
    h5 = mkh5.mkh5(TEST_RAW_MKH5_FILE)
    for dblock_path in h5.dblock_paths:
        hdr, _ = h5.get_dblock(dblock_path)
        mkh5mne._parse_hdr_for_mne(hdr)


@pytest.mark.parametrize(
    "garv_anns",
    [
        None,
        GARV_ANNOTATIONS_MS,
        pytest.param(GARV_ANNOTATIONS_BAD, marks=pytest.mark.xfail(strict=True)),
    ],
)
@pytest.mark.parametrize("mkh5_f", [TEST_RAW_MKH5_FILE, TEST_EPOCHS_MKH5_FILE])
def test__dblock_to_raw(mkh5_f, garv_anns):
    h5 = mkh5.mkh5(mkh5_f)
    for dblock_path in h5.dblock_paths:
        mkh5mne._dblock_to_raw(mkh5_f, dblock_path, garv_annotations=garv_anns)


def test__is_equal_mne_info():
    h5 = mkh5.mkh5(TEST_RAW_MKH5_FILE)
    dblock_paths = h5.dblock_paths

    hdr_a, dblock_a = h5.get_dblock(dblock_paths[0])
    hdr_b, dblock_b = h5.get_dblock(dblock_paths[1])

    info_a, montage_a = mkh5mne._hdr_dblock_to_info_montage(hdr_a)
    info_b, montage_b = mkh5mne._hdr_dblock_to_info_montage(hdr_b)

    # a and b are different crws, same YAML apparatus

    # same, different info
    assert mkh5mne._is_equal_mne_info(info_a, info_a)
    assert not mkh5mne._is_equal_mne_info(info_a, info_b)
    assert mkh5mne._is_equal_mne_info(info_a, info_b, exclude=["subject_info"])

    # same, different montage
    assert mkh5mne._is_equal_mne_montage(montage_a, montage_a)
    assert mkh5mne._is_equal_mne_montage(montage_a, montage_b)

    # corrupted montage
    montage_b_bad = deepcopy(montage_b)
    for bad_key in montage_b_bad.__dict__.keys():
        # reset for testing
        montage_b_bad = deepcopy(montage_b)
        setattr(montage_b_bad, bad_key, "X")
        result = mkh5mne._is_equal_mne_montage(montage_a, montage_b_bad, verbose=True)
        assert result is False


# ------------------------------------------------------------
# User API tests

def test_read_raw_epochs_mkh5():
    mkh5mne.read_raw_mkh5(TEST_EPOCHS_MKH5_FILE)


@pytest.mark.parametrize(
    "dbps",
    [
        None,
        ["open/dblock_0"],
        pytest.param(
            ["open/dblock_X"],
            marks=pytest.mark.xfail(strict=True, reason=mkh5mne.Mkh5DblockPathError),
        ),
        pytest.param(37.2, marks=pytest.mark.xfail(strict=True, reason=TypeError)),
        pytest.param([1, 2, 3], marks=pytest.mark.xfail(strict=True, reason=TypeError)),
    ],
)
def test_read_raw_mkh5(dbps):
    mkh5mne.read_raw_mkh5(TEST_RAW_MKH5_FILE, dblock_paths=dbps)


def test_read_raw_mkh5_apparatus_yaml():
    mkh5mne.read_raw_mkh5(TEST_RAW_MKH5_FILE, apparatus_yaml=TEST_APPARATUS_YAML)


def test_read_raw_mkh5_duplicate_mne_raw_tick():
    # mkpy epochs allow one-many event tags, MNE metadata
    # must be 1-1 with mne.Raw["event_channel} events: [sample, 0, event]

    # dont trash the test file ...
    dupe_f = Path(DATA_DIR / "_dupe.h5")
    dupe_f.write_bytes(Path(TEST_EPOCHS_MKH5_FILE).read_bytes())

    h5 = mkh5.mkh5(dupe_f)
    event_table = h5.get_event_table(DATA_DIR / "sub000p3_bindesc.txt")
    event_table_2 = pd.concat([event_table.iloc[:3, :], event_table])
    h5.set_epochs("dup_events", event_table_2, tmin_ms=-10, tmax_ms=10)

    with pytest.raises(ValueError):
        mkh5mne.read_raw_mkh5(dupe_f)

    dupe_f.unlink()


@pytest.mark.parametrize("garv_anns", [GARV_ANNOTATIONS_MS, None])
def test_read_write_raw(garv_anns):

    infix = "_".join(str(val) for val in garv_anns.values()) if garv_anns else "None"
    raw_fif = Path(DATA_DIR / f"_test_read_write_garv_{infix}-raw.fif")
    print("read/write test writing:", raw_fif)
    raw_w = mkh5mne.read_raw_mkh5(
        TEST_EPOCHS_MKH5_FILE, garv_annotations=garv_anns)
    raw_w.save(raw_fif, overwrite=True)
    raw_r = mne.io.read_raw_fif(raw_fif, preload=True)

    # time stamps will differ in info["file_id"] == info["meas_id"]
    assert mkh5mne._is_equal_mne_info(
        raw_w.info, raw_r.info, exclude=["file_id", "meas_id"]
    )

    # data
    assert np.allclose(raw_w.get_data(), raw_r.get_data())

    # event and optional garv annotations
    assert all(raw_w.annotations.description == raw_r.annotations.description)
    for attr in ["onset", "duration"]:
        assert np.allclose(
            getattr(raw_w.annotations, attr), getattr(raw_r.annotations, attr)
        )


def test_get_garv_bads():

    onsets = [44.048, 45.176, 54.112, 63.556, 96.576, 103.392, 118.416]
    durations = [0.024, 0.024, 0.024, 0.024, 0.024, 0.024, 0.024]
    descriptions = ["BAD_garv_48"] * 3 + ["BAD_garv_32"] + ["BAD_garv_48"] * 3
    dbps = mkh5.mkh5(TEST_EPOCHS_MKH5_FILE).dblock_paths
    raw_mkh5 = mkh5mne.read_raw_mkh5(
        TEST_EPOCHS_MKH5_FILE, dblock_paths=dbps[:1],  # one block to shorten test time
    )
    bad_garvs = mkh5mne.get_garv_bads(
        raw_mkh5, event_channel="ms100", tmin=-12, tmax=12, units="ms",
    )
    assert all(bad_garvs.onset == onsets)
    assert all(bad_garvs.duration == durations)
    assert all(bad_garvs.description == descriptions)


def test_get_epochs():
    """smoke test get_mkh5_epochs which also traverses get_epochs_metadata"""

    dbps = mkh5.mkh5(TEST_EPOCHS_MKH5_FILE).dblock_paths
    raw_mkh5 = mkh5mne.read_raw_mkh5(
        TEST_EPOCHS_MKH5_FILE, dblock_paths=dbps[0:1],  # one block to shorten test time
    )

    metadata = mkh5mne.get_epochs_metadata(raw_mkh5, epochs_name="ms100")
    epochs = mkh5mne.get_epochs(
        raw_mkh5,
        epochs_name="ms100",
        baseline=(None, 0),  # mne syntax for prestim baseline
        preload=True,
    )
    assert all(epochs.metadata.columns == metadata.columns)

    coi = [
        "epoch_id",
        "data_group",
        "dblock_path",
        "dblock_ticks",
        "mne_dblock_path_idx",
        "mne_raw_tick",
        "match_tick",
        "anchor_tick",
        "diti_t_0",
        "diti_hop",
        "diti_len",
        "instrument",
        "bin",
        "tone",
        "stim",
        "log_evcodes",
        "log_flags",
        "log_ccodes",
        "regexp",
        "match_time",
        "match_code",
        "anchor_code",
        "accuracy",
        "acc_type",
    ]
    epochs_coi = mkh5mne.get_epochs(raw_mkh5, epochs_name="ms100", metadata_columns=coi)
    assert all(epochs_coi.metadata.columns == coi)


def test_find_mkh5_events():
    """test mkh5 event channels from dig, mkpy, and mkpy epochs"""

    # precomputed from TEST_EPOCHS_MKH5_FILE
    checksums = {
        "raw_evcodes":  ((706, 3), [61501701, 0, 28597]),
        "log_evcodes": ((706, 3), [61501701, 0, 28597]),
        "log_ccodes": ((496, 3), [31533000, 0, 496]),
        "log_flags": ((103, 3), [6383620, 0, 4144]),
        "pygarv": ((0, 3), [0, 0, 0]),
        "ms1500": ((600, 3),  [54650754, 0, 6515]),
    }

    mne_raw = mkh5mne.read_raw_mkh5(TEST_EPOCHS_MKH5_FILE)

    for key, val in checksums.items():
        events_array = mkh5mne.find_mkh5_events(mne_raw, key)
        assert val[0] == events_array.shape
        assert all(val[1] == events_array.sum(axis=0))
        
    # not found channels are ValueError
    with pytest.raises(ValueError):
        mkh5mne.find_mkh5_events(mne_raw, "NoSuchChannel")

    # not MNE stime channels are TypeErrors
    with pytest.raises(TypeError):
        mkh5mne.find_mkh5_events(mne_raw, "MiPa")


