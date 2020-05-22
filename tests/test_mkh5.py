"""test module for primary mkh5 class methods and attributes"""

import pytest
import pandas as pd
import numpy as np
import h5py
import pprint
import os
import copy
import contextlib
import io
import re
from pathlib import Path

from .config import (
    TEST_DIR,
    TEST_H5,
    IRB_DIR,
    GET_IRB_MKDIG,
    CAL_ARGS,
    S01,
    S05,
    CALSTEST,
    irb_data,
    mkpy,
)

from mkpy import mkh5, h5tools


# CRUD tests
# ------------------------------------------------------------
# mkh5 initialization tests
# cases:
#   * h5 file does not exist ... create empty for writing
#   * h5 file exists ... open for read only


@pytest.mark.parametrize("h5f", [str(TEST_H5), Path(TEST_H5)])
def test_init(h5f):
    """test file creation and .h5 validity, must warn if file is unwritable."""

    # file should not exist already
    # h5f = Path('data/test_init.h5')
    if Path(h5f).exists():
        os.remove(h5f)

    # file should be created
    mkh5.mkh5(h5f)
    assert Path(h5f).is_file()

    # file must be a valid .h5 file
    with h5py.File(h5f, "r") as h5:
        assert h5.id.valid == 1

    # user should be warned if file is unwritable
    os.chmod(h5f, 0o400)
    with pytest.warns(UserWarning):
        mkh5.mkh5(h5f)

    # cleanup
    os.remove(h5f)


def test_reset_all():
    """test reset_all, which must delete the contents of a file."""

    # file should not exist already
    # h5f = TEST_DIR('data/test_reset_all.h5')
    if TEST_H5.exists():
        os.remove(TEST_H5)

    # new file should be empty
    mydat = mkh5.mkh5(TEST_H5)
    with h5py.File(TEST_H5, "r") as h5:
        assert not h5.keys(), f"Keys found: {h5.keys()}, expected no keys."

    # add group so we can check that reset_all wipes it
    with h5py.File(TEST_H5, "r+") as h5:
        h5.create_group("test_group")
        assert h5.keys(), f"Expected to see test_group, but keys are empty."

    # reset_all should make the file empty again
    mydat.reset_all()
    with h5py.File(TEST_H5, "r") as h5:
        assert not h5.keys(), f"Keys found: {h5.keys()}, expected no keys."

    # cleanup
    os.remove(TEST_H5)


def test_create_mkdata():
    """mkh5 data loader test"""

    try:
        mydat = mkh5.mkh5(TEST_H5)
        mydat.reset_all()
        mydat.create_mkdata(
            S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"]
        )
    except Exception as fail:
        raise fail

    os.remove(TEST_H5)


def test_create_mkdata_hdf5_options():

    """mkh5 data converter, of limited interest b.c. compressed data I/O
    is brutally slow

    """
    # chunks, shuffle, error checking options not tested
    try:
        mydat = mkh5.mkh5(TEST_H5)
        mydat.reset_all()  # start fresh
        mydat.create_mkdata(
            S01["gid"],
            S01["eeg_f"],
            S01["log_f"],
            S01["yhdr_f"],
            compression="gzip",
        )
    except Exception as fail:
        print("mkh5.create_mkdata() failed")
        raise fail

    os.remove(TEST_H5)


@pytest.mark.parametrize(
    "yhdr",
    [
        S01["yhdr_f"],
        pytest.param(
            TEST_DIR("data/26chan_bad_yaml.yhdr"),
            marks=pytest.mark.xfail(
                raises=mkpy.mkh5.mkh5.YamlHeaderFormatError
            ),
        ),
        pytest.param(
            TEST_DIR("data/26chan_bad_locs.yhdr"),
            marks=pytest.mark.xfail(
                raises=mkpy.mkh5.mkh5.YamlHeaderFormatError
            ),
        ),
    ],
)
def test_load_yhdr(yhdr):
    """load good yaml header files, fail informatively on bad"""

    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()

    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], yhdr)
    os.remove(TEST_H5)


def test_create_expt():
    """mkh5 data multiple crw/log loader test"""

    mydat = mkh5.mkh5(TEST_H5)  # start fresh
    mydat.reset_all()
    for fs in [S01, S05]:
        mydat.create_mkdata(fs["gid"], fs["eeg_f"], fs["log_f"], fs["yhdr_f"])
    os.remove(TEST_H5)


def test_inspectors():
    """test dataset attribute headinfo and info dumps"""

    # ------------------------------------------------------------
    # single subject file
    # ------------------------------------------------------------
    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()

    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])
    mydat.calibrate_mkdata(S01["gid"], **CAL_ARGS)

    assert len(re.findall(r"(S01)", mydat.info())) == 972

    # capture headinfo
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        mydat.headinfo()
    assert len(re.findall(r"S01", f.getvalue())) == 971
    f.close()

    # ------------------------------------------------------------
    # multiple subject experiment with headinfo selection
    # ------------------------------------------------------------
    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()
    for expt in ["expt1", "expt2"]:
        for fs in [S01, S05]:
            mydat.create_mkdata(
                expt + "/" + fs["gid"], fs["eeg_f"], fs["log_f"], fs["yhdr_f"]
            )
    assert len(re.findall(r"(S0[15])", mydat.info())) == 1968

    # test headinfo and info for multiexpt
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        mydat.headinfo()
    assert len(re.findall(r"S0[15]", f.getvalue())) == 1964
    f.close()

    # ------------------------------------------------------------
    # headinfo pattern selection
    # ------------------------------------------------------------
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        mydat.headinfo("expt2")
    expt2_hinfo = f.getvalue()
    assert all(
        [
            re.match(r"(^expt2|^$)", x) is not None
            for x in expt2_hinfo.split("\n")
        ]
    )
    assert all(
        [re.match(r"(^expt1)", x) is None for x in expt2_hinfo.split("\n")]
    )

    # illegal ... should return None and raise warning
    bad_chooser1 = "samplerate/S05"  # wrong order
    bad_hinfo = mydat.headinfo(bad_chooser1)
    if bad_hinfo is not None:
        raise Exception("mkh5.headinfo failed to catch bad h5_path")

    os.remove(TEST_H5)  # cleanup


def test_get_set_head():
    """test public header CRUD via slashpath """

    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()
    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])

    # test get->set->get round trip
    head_pattern = "S01/dblock_0/streams/MiPa/"
    before_head = mydat.gethead(head_pattern)
    mydat.sethead(before_head)
    after_head = mydat.gethead(head_pattern)
    assert before_head == after_head

    # test get-set with changes
    print("# ------------------------------------------------------------")
    print("# Before sethead ...")
    print("# ------------------------------------------------------------")
    mydat = mkh5.mkh5(TEST_H5)  # re-open w/out obliteration
    mydat.headinfo("S01/dblock_0.*(experiment\b|dblock_ticks|crw_ticks)")
    mydat.sethead(
        [
            ("S01/dblock_0/streams/dblock_ticks/new_key", "new_value"),
            ("S01/dblock_0/streams/dblock_ticks/name", "new_dblock_ticks"),
            ("S01/dblock_0/streams/crw_ticks/stream", "new_crw_ticks"),
            ("S01/dblock_0/experiment", "new_expt_name"),
            ("S01/dblock_0/runsheet/new_data", [1, 2, 3]),
            ("S01/dblock_0/streams/dblock_ticks/name", "new_dblock_ticks"),
        ]
    )
    print("# ------------------------------------------------------------")
    print("# After sethead ...")
    print("# ------------------------------------------------------------")

    mydat = mkh5.mkh5(TEST_H5)  # re-open w/out obliteration
    mydat.headinfo("S01/dblock_0.*(experiment\b|dblock_ticks|crw_ticks)")

    # inspect via h5py directly
    hio = mydat.HeaderIO()
    with h5py.File(TEST_H5, "r") as h5:
        myblock = h5[S01["gid"] + "/dblock_0"]
        hio.get(myblock)
        for c in ["dblock_ticks", "crw_ticks", "MiPa"]:
            pprint.pprint(hio.header["streams"][c])

    mydat = mkh5.mkh5(TEST_H5)  # re-open w/out obliteration
    new_info = mydat.gethead(
        "S01/dblock_0.*(experiment|(MiPa|dblock_ticks|crw_ticks))"
    )
    test_vals = [
        (k, v)
        for k, v in new_info
        if "dblock_0/streams" in k or "/experiment" in k
    ]
    h5_path = "S01/dblock_0"
    for k, v in test_vals:
        # print(k)
        if k == h5_path + "/experiment" and v != "new_expt_name":
            msg = (
                "sethead failed to assign key=value: "
                "experiment='new_expt_name'"
            )
            raise ValueError(msg)
        if (
            k == h5_path + "streams/dblock_ticks/name"
            and v != "new_dblock_ticks"
        ):
            msg = "sethead failed to assign {0} new_dblock_ticks: {1}".format(
                k, v
            )
            raise ValueError(msg)
        if k == h5_path + "streams/crw_ticks/stream" and v != "new_crw_ticks":
            msg = "sethead failed to assign {0}: new_crw_ticks".format(k, v)
            raise ValueError(msg)
        if k == h5_path + "streams/dblock_ticks/new_key" and v != "new_value":
            msg = "sethead failed to create new {0}: {1}d".format(k, v)
            raise ValueError(msg)
    os.remove(TEST_H5)


# ------------------------------------------------------------
# test calibration to uV

# TO DO ...
#  * replace log poked cals test with non-irb test data
#  * replace flat cals with non-irb test data
#  * open channel cals test
# ------------------------------------------------------------


def test_plotcals():
    """calibration param inspector routine with sensible default values"""

    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])

    # This is a pre-calibration inspector ... viewer only like garv
    mydat.plotcals(TEST_H5, S01["gid"], **CAL_ARGS)

    os.remove(TEST_H5)


def test_calibrate_mkdata_use_cals_2():
    """ draw from adlong """
    mkh5_dir = Path(TEST_DIR("data"))
    resting_dir = mkh5_dir
    cals_dir = mkh5_dir
    subid = "s001"
    for state in ["ro", "rc"]:
        datagroup = subid + state

        h5_f = mkh5_dir / (datagroup + ".h5")  # h5 filename
        this_h5 = mkh5.mkh5(h5_f)
        this_h5.reset_all()

        # 2. load .crw/.log data into .h5 file
        crw_f = resting_dir / (datagroup + ".crw")
        log_f = resting_dir / (datagroup + ".log")
        yhdr_f = mkh5_dir / (datagroup + ".yhdr")
        this_h5.create_mkdata(datagroup, crw_f, log_f, yhdr_f)

        # 3. load up cals into the same file in a *sister* datagroup
        cals = datagroup + "_cals"
        cal_crw_f = cals_dir / (subid + "c.crw")
        cal_log_f = cals_dir / (subid + "c.log")
        this_h5.create_mkdata(cals, cal_crw_f, cal_log_f, yhdr_f)

        # optionally plot the cals
        pts, pulse, lo, hi, ccode = 3, 10, -32, 32, 0
        plot_cals = False
        if plot_cals:
            f, ax = this_h5.plotcals(
                h5_f,
                cals,
                n_points=pts,  # pts to average
                cal_size=pulse,  # uV
                lo_cursor=lo,  # lo_cursor ms
                hi_cursor=hi,  # hi_cursor ms
                cal_ccode=ccode,  # condition code
            )
            p = plt.show(f)

        # calibrate w/ the same params
        this_h5.calibrate_mkdata(
            datagroup,
            n_points=pts,
            cal_size=pulse,
            lo_cursor=lo,
            hi_cursor=hi,
            cal_ccode=ccode,
            use_cals=cals,
        )  # Ithis points to the cals data group

        os.remove(h5_f)


def test_create_and_cal_then_append_and_cal():
    """test create, calibrate, append more, calibrate again"""

    mydat = mkh5.mkh5(TEST_H5)  # start fresh
    mydat.reset_all()

    # build data file with S01, S05
    for fs in [S01, S05]:
        mydat.create_mkdata(fs["gid"], fs["eeg_f"], fs["log_f"], fs["yhdr_f"])

    # calibrate S01 *only*
    mydat.calibrate_mkdata(S01["gid"], **CAL_ARGS)

    # 3. *NOW* append some more raw data *after* calibration ... why
    # on earth?

    mydat.append_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])

    # 4. go back and S01 again, should skip dblock_0 and
    # just report dblock_1
    cal_args = copy.copy(CAL_ARGS)
    cal_args["use_cals"] = "S05"
    mydat.calibrate_mkdata(S01["gid"], **cal_args)
    os.remove(TEST_H5)


# ------------------------------------------------------------
# tests below here run on IRB protected data outside the repo
# ------------------------------------------------------------


@irb_data
def test_irb_append_mkdata():
    """test appending separate .crw/.log to a data group: use case
    separate cals, split sessions.
    """

    pfx = "test1"
    pfxcals = "test1cals"

    h5f = IRB_DIR / "mkh5" / "test_append_mkdata.h5"

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))

    mydat.append_mkdata(pfx, *GET_IRB_MKDIG(pfxcals))
    os.remove(h5f)


@irb_data
def test_irb_calibrate_same_crw():

    pfx = "test2"
    h5f = IRB_DIR / "mkh5" / "test_calibrate_same_crw.h5"
    stub_h5f = TEST_DIR("data/stub.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh

    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    mydat.calibrate_mkdata(pfx, **CAL_ARGS)

    # report calibration scale factors direct from hdf5 file
    with h5py.File(h5f, "r") as h5:
        subid = pfx
        dblock_names = [
            subid + "/dblock_" + str(b) for b in range(len(h5[subid].keys()))
        ]
        lo_gain_chans = ["lle", "lhz", "rle", "rhz", "MiPf", "LLPf", "RLPf"]
        stub = mkh5.mkh5(stub_h5f)
        hio = stub.HeaderIO()
        for dblock_name in dblock_names:
            hio.get(h5[dblock_name])
            strms = hio.header["streams"]
            for k, v in strms.items():
                if "dig_chan_" in v["source"]:
                    scale_by = None
                    scale_by = v["cals"]["scale_by"]
                    print(
                        "{0} {1:4s} {2:5.3f}".format(
                            subid, v["name"], scale_by
                        )
                    )

    # ensure calibrating twice throws an error ...
    try:
        mydat.calibrate_mkdata(subid, **CAL_ARGS)
    except Exception as fail:
        print("OK ... caught attempted double calibration")
    else:
        raise RuntimeError(
            "uh oh ... failed to catch an attempted double calibration"
        )
    os.remove(h5f)
    os.remove(stub_h5f)


@irb_data
def test_irb_calibrate_mkdata_use_cals():
    """test using cals from dblocks in another group"""

    h5f = IRB_DIR / "mkh5" / "calibrate_mkdata_use_cals.h5"

    pfx1 = "test1"
    pfx2 = "test2"

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(pfx1, *GET_IRB_MKDIG(pfx1))
    mydat.create_mkdata(pfx2, *GET_IRB_MKDIG(pfx2))

    pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
    cal_args = copy.copy(CAL_ARGS)
    cal_args["use_cals"] = pfx2
    mydat.calibrate_mkdata(pfx1, **cal_args)
    os.remove(h5f)


@irb_data
def test_irb_calibrate_mkdata_appended_cals():
    """test appending separate cals"""

    h5f = IRB_DIR / "mkh5" / "calibrate_mkdata_appended_cals.h5"
    pfx = "test1"
    pfxcals = "test1cals"

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))

    # this should fail, make sure it does
    try:
        mydat.calibrate_mkdata(pfx, **CAL_ARGS)
    except Exception as fail:
        print(fail.args[0])
        print("Caught missing cals")

    # add the cal block and try again ...
    mydat.append_mkdata(pfx, *GET_IRB_MKDIG(pfxcals))
    mydat.calibrate_mkdata(pfx, **CAL_ARGS)
    os.remove(h5f)


@irb_data
def test_irb_calibrate_mkdata_use_file():
    """test using cals from dblocks in another file"""

    # make first h5 file
    pfx1 = "test1"
    h5f1 = IRB_DIR / "mkh5" / "calibrate_mkdata_use_file1.h5"

    mydat1 = mkh5.mkh5(h5f1)
    mydat1.reset_all()
    mydat1.create_mkdata(pfx1, *GET_IRB_MKDIG(pfx1))

    # make second h5 file
    pfx2 = "test2"
    h5f2 = IRB_DIR / "mkh5" / "calibrate_mkdata_use_file2.h5"

    mydat2 = mkh5.mkh5(h5f2)
    mydat2.reset_all()  # start fresh
    mydat2.create_mkdata(pfx2, *GET_IRB_MKDIG(pfx2))

    # calibrate first with cals from second
    cal_args = copy.copy(CAL_ARGS)
    cal_args["use_cals"] = pfx2
    cal_args["use_file"] = h5f2
    mydat1.calibrate_mkdata(pfx1, **cal_args)

    os.remove(h5f1)
    os.remove(h5f2)


@irb_data
def test_irb_negative_raw_evcodes():
    """the mkh5 dblocks are split at pause marks defined as -16834 ... anything else
    should throw a warning.
    """

    pfx = "lexcon01"

    h5f = IRB_DIR / "mkh5" / (pfx + ".h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    # print(mydat.info()) # very long
    os.remove(h5f)


@irb_data
def test_irb_event_code_0_in_log():
    """crw 0's are non-event sample, log 0's shouldn't exist but occasionally do"""

    pfx = "cor03"

    h5f = IRB_DIR / "mkh5" / (pfx + ".h5")

    try:
        mydat = mkh5.mkh5(h5f)
        mydat.reset_all()  # start fresh
        mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    except Exception as fail:
        print("mkh5.create_mkdata() failed")
        raise fail

    os.remove(h5f)


@irb_data
def test_irb_flat_cals():

    pfx = "lexcon02"
    h5f = IRB_DIR / "mkh5" / (pfx + ".h5")

    myh5 = mkh5.mkh5(h5f)  # start fresh
    myh5.reset_all()
    myh5.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))

    # # use same as calstest.sh
    pts, pulse, lo, hi, ccode = 3, 10, -30, 30, 0
    try:
        myh5.calibrate_mkdata(
            pfx,
            n_points=pts,  # pts to average, either side of cursor
            cal_size=pulse,  # uV
            lo_cursor=lo,  # lo_cursor ms
            hi_cursor=hi,  # hi_cursor ms
            cal_ccode=ccode,
            use_cals=None,
        )
    except ValueError as fail:
        fail_msg = fail.args[0]
        if (
            "lexcon02.h5 channel 28:A2 has no cal pulses after "
            "trimming at median +/- 1.5IQR"
        ) in fail_msg:
            print("OK ... caught flat cals")
        else:
            print("failed to catch flat cals")
            raise


@irb_data
def test_irb_calibrate_negative_cals():
    """test that calibration don't care that the pulse step is negative going. Spot checks MiPa"""

    pfx = "arquant3"
    h5f = IRB_DIR / "mkh5" / "negative_cals_test.h5"

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    with h5py.File(h5f, "r") as h5:
        MiPa_before = h5[pfx + "/dblock_0"]["MiPa"]

    mydat.calibrate_mkdata(
        pfx,
        n_points=3,  # pts to average, either side of cursor
        cal_size=10,  # uV
        polarity=1,  # of calibration pulse
        lo_cursor=-50,  # ms
        hi_cursor=50,
        cal_ccode=0,
        use_cals=None,
    )
    with h5py.File(h5f, "r") as h5:
        MiPa_after = h5[pfx + "/dblock_0"]["MiPa"]
    assert all(np.sign(MiPa_before) == np.sign(MiPa_after))
    # polarity of data heads/tails should be the same
    # pprint.pprint(mydat.info()) # visual check


@irb_data
def test_irb_calibrate_logpoked_cals():
    """test that calibration ignores logpoked cals"""

    pfx = "arquant2"
    h5f = IRB_DIR / "mkh5" / "logpoked_cals_test.h5"
    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # a = read/write, create if needed
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    mydat.calibrate_mkdata(
        pfx,
        n_points=3,  # pts to average, either side of cursor
        cal_size=10,  # uV
        polarity=1,  # of calibration pulse
        lo_cursor=-50,  # ms
        hi_cursor=50,
        cal_ccode=0,
        use_cals=None,
    )

    hio = mydat.HeaderIO()
    dblock_paths = h5tools.get_dblock_paths(h5f, pfx)
    lo_gain_chans = ["lle", "lhz", "rle", "rhz", "MiPf", "LLPf", "RLPf"]

    with h5py.File(h5f, "r+") as h5:
        for dbp in dblock_paths:
            dblock = h5[dbp]
            hio.get(dblock)
            streams = hio.header["streams"]
            for k, stream in streams.items():
                if "dig_chan_" in stream["source"]:
                    scale_by = None
                    scale_by = abs(stream["cals"]["scale_by"])
                    if stream["name"] in lo_gain_chans:
                        assert 17.0 < scale_by and scale_by < 22.0
                    else:
                        assert 34.0 < scale_by and scale_by < 44.0


def test_mkh5_correctness():
    """verify dtypes and spot check A/D samples and calibrated microvolts"""

    dblock_dtype = np.dtype(
        [
            ("dblock_ticks", "<u4"),
            ("crw_ticks", "<u4"),
            ("raw_evcodes", "<i2"),
            ("log_evcodes", "<i2"),
            ("log_ccodes", "<u2"),
            ("log_flags", "<u2"),
            ("pygarv", "<u8"),
            ("lle", "<f2"),
            ("lhz", "<f2"),
            ("MiPf", "<f2"),
            ("LLPf", "<f2"),
            ("RLPf", "<f2"),
            ("LMPf", "<f2"),
            ("RMPf", "<f2"),
            ("LDFr", "<f2"),
            ("RDFr", "<f2"),
            ("LLFr", "<f2"),
            ("RLFr", "<f2"),
            ("LMFr", "<f2"),
            ("RMFr", "<f2"),
            ("LMCe", "<f2"),
            ("RMCe", "<f2"),
            ("MiCe", "<f2"),
            ("MiPa", "<f2"),
            ("LDCe", "<f2"),
            ("RDCe", "<f2"),
            ("LDPa", "<f2"),
            ("RDPa", "<f2"),
            ("LMOc", "<f2"),
            ("RMOc", "<f2"),
            ("LLTe", "<f2"),
            ("RLTe", "<f2"),
            ("LLOc", "<f2"),
            ("RLOc", "<f2"),
            ("MiOc", "<f2"),
            ("A2", "<f2"),
            ("rhz", "<f2"),
            ("rle", "<f2"),
            ("heog", "<f2"),
        ]
    )

    # check after calibration to 3 decimal places
    samples_0 = (
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        2.0,
        4.0,
        -5.0,
        -4.0,
        0.0,
        0.0,
        1.0,
        3.0,
        -4.0,
        2.0,
        2.0,
        1.0,
        2.0,
        2.0,
        3.0,
        3.0,
        -1.0,
        -2.0,
        1.0,
        2.0,
        4.0,
        0.0,
        0.0,
        -1.0,
        -7.0,
        3.0,
        -2.0,
        0.0,
        7.0,
        4.0,
        0.0,
        5.0,
    )

    samples_n = (
        28159,
        28159,
        -16384,
        -16384,
        0,
        0,
        0,
        1.0,
        1.0,
        -3.0,
        0.0,
        -1.0,
        2.0,
        0.0,
        2.0,
        0.0,
        2.0,
        1.0,
        -1.0,
        3.0,
        0.0,
        3.0,
        0.0,
        -4.0,
        -1.0,
        2.0,
        2.0,
        1.0,
        0.0,
        2.0,
        -2.0,
        -17.0,
        -1.0,
        -1.0,
        0.0,
        -3.0,
        0.0,
        -4.0,
        2.0,
    )

    # after calibration to 3 decimal places
    muv_0 = (
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        3.492,
        6.516,
        -8.125,
        -6.754,
        0.0,
        0.0,
        1.7705,
        4.94,
        -6.695,
        3.316,
        3.264,
        1.743,
        3.312,
        3.371,
        4.99,
        4.957,
        -1.791,
        -3.479,
        1.656,
        3.408,
        6.613,
        0.0,
        0.0,
        -1.669,
        -11.66,
        4.97,
        -3.287,
        0.0,
        11.766,
        6.57,
        0.0,
        8.71,
    )

    muv_n = (
        28159,
        28159,
        -16384,
        -16384,
        0,
        0,
        0,
        1.746,
        1.629,
        -4.875,
        0.0,
        -1.698,
        3.342,
        0.0,
        3.295,
        0.0,
        3.316,
        1.632,
        -1.743,
        4.97,
        0.0,
        4.99,
        0.0,
        -7.164,
        -1.739,
        3.312,
        3.408,
        1.653,
        0.0,
        3.258,
        -3.338,
        -28.31,
        -1.656,
        -1.644,
        0.0,
        -5.043,
        0.0,
        -6.918,
        3.484,
    )

    n_cols = len(dblock_dtype)

    # convert .crw/.log to HDF5
    mydat = mkh5.mkh5(TEST_H5)
    mydat.reset_all()
    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])

    hdr, dblock = mydat.get_dblock("S01/dblock_0")

    assert dblock.shape == (28160,)  # rows
    assert dblock.dtype == dblock_dtype
    assert all([samples_0[i] == dblock[0][i] for i in range(n_cols)])
    assert all([samples_n[i] == dblock[-1][i] for i in range(n_cols)])

    mydat.calibrate_mkdata(S01["gid"], **CAL_ARGS)
    hdr, muv_dblock = mydat.get_dblock("S01/dblock_0")

    assert all(
        [
            np.isclose(muv_0[i], muv_dblock[0][i], rtol=1e-3)
            for i in range(n_cols)
        ]
    )
    assert all(
        [
            np.isclose(muv_n[i], muv_dblock[-1][i], rtol=1e-3)
            for i in range(n_cols)
        ]
    )

    os.remove(TEST_H5)


wle_valerr = pytest.mark.xfail(strict=True, raises=ValueError)
wle_runerr = pytest.mark.xfail(strict=True, raises=RuntimeError)


@pytest.mark.parametrize(
    "log_f,wle",
    [
        # correct log file
        pytest.param(S01["log_f"], None),  # default mkpy.mkh5 <= 0.2.2
        pytest.param(S01["log_f"], "aligned"),
        pytest.param(S01["log_f"], "as_is"),
        # incorrect same-length log file (S05) must fail on default,
        # and explicit "aligned", pass "as_is"
        pytest.param(S05["log_f"], None, marks=wle_runerr),
        pytest.param(S05["log_f"], "aligned", marks=wle_runerr),
        pytest.param(S05["log_f"], "as_is"),  # risky but allowed
        # can't give a log file and not use it
        pytest.param(S01["log_f"], "from_eeg", marks=wle_valerr),
        pytest.param(S01["log_f"], "none", marks=wle_valerr),
        # log_f is None
        pytest.param(None, "from_eeg"),
        pytest.param(None, "none"),
        # bad log_f, with_log_events arg combinations should all fail
        pytest.param(None, None, marks=wle_valerr),
        pytest.param(None, "aligned", marks=wle_valerr),
        pytest.param(None, "as_is", marks=wle_valerr),
        # over length wrong log throws truncation warning, fails properly on
        # event tick mismatch
        pytest.param(CALSTEST["log_f"], None, marks=wle_runerr),
    ],
)
def test_with_log_events(log_f, wle):
    def read_log_txt(log_f_txt):
        log_data = pd.read_csv(log_f_txt, sep="\s+")[
            ["evtcode", "clock_ticks", "ccode", "flags"]
        ]
        return log_data

    sid = S01["gid"]
    eeg_f = S01["eeg_f"]
    yhdr_f = S01["yhdr_f"]

    wle_test = mkh5.mkh5(TEST_H5)
    wle_test.reset_all()
    if wle is None:
        wle_test.create_mkdata(sid, eeg_f, log_f, yhdr_f)
        wle_test.append_mkdata(sid, eeg_f, log_f, yhdr_f)
    else:
        wle_test.create_mkdata(sid, eeg_f, log_f, yhdr_f, with_log_events=wle)
        wle_test.append_mkdata(sid, eeg_f, log_f, yhdr_f, with_log_events=wle)

    # check correctness
    if log_f is not None:
        log_data = read_log_txt(str(log_f) + ".txt")

    dbpaths = wle_test.dblock_paths
    for dbpath in dbpaths:
        _, data = wle_test.get_dblock(wle_test.dblock_paths[0])
        dblock_raw_evcodes = data[data["raw_evcodes"] != 0]["raw_evcodes"]
        dblock_log_evcodes = data[data["log_evcodes"] != 0]["log_evcodes"]

        # read log codes from data file and confirm they match the
        # logcat2 text dumps
        if wle in ["as_is"]:
            assert all(
                dblock_log_evcodes
                == log_data["evtcode"][: len(dblock_log_evcodes)]
            )

        if wle is "from_eeg":
            assert all(dblock_raw_evcodes == dblock_log_evcodes)

        if wle is "none":
            for col in ["log_evcodes", "log_ccodes", "log_flags"]:
                assert all(
                    np.equal(0, data[col])
                ), f"non-zero values in {col} with_log_events='none'"

    os.remove(TEST_H5)


@irb_data
@pytest.mark.parametrize(
    "wle,log_f",
    [
        pytest.param(
            None, "sarc_cal525.log", marks=pytest.mark.xfail(strict=True)
        ),
        pytest.param(
            "aligned", "sarc_cal525", marks=pytest.mark.xfail(strict=True)
        ),
        pytest.param("as_is", "sarc_cal525.log"),
        pytest.param("from_eeg", None),
        pytest.param("none", None),
    ],
)
def test_irb_load_bad_log(wle, log_f):
    """seana's split-session Sarcasm files"""

    crw_f = IRB_DIR / "mkdig/sarc_cal525.crw"
    if log_f is not None:
        log_f = IRB_DIR / "mkdig" / log_f
    yhdr_f = IRB_DIR / "mkdig/sarc01.yhdr"

    h5f = IRB_DIR / "mkh5" / "test_load_bad.h5"
    pfx = "sarc01"

    sarc01 = mkh5.mkh5(h5f)
    sarc01.reset_all()

    if wle is None:
        # default is "aligned", this should fail
        sarc01.create_mkdata(pfx, crw_f, log_f, yhdr_f)
        sarc01.append_mkdata(pfx, crw_f, log_f, yhdr_f)
    else:
        sarc01.create_mkdata(pfx, crw_f, log_f, yhdr_f, with_log_events=wle)
        sarc01.append_mkdata(pfx, crw_f, log_f, yhdr_f, with_log_events=wle)


# def test_LocDat():

#     print("testing LocDat 3-D cartesian x,y,z")
#     x = 1.0; y = 2.5; z = -3.1
#     mylocdat = mkh5.LocDat('electrode', 'lle',
#                             'cartesian', [1.0, 2.5,-3.1],
#                             distance_units = 'cm')
#     assert(np.isclose(mylocdat.x, x))
#     assert(np.isclose(mylocdat.y, y))
#     assert(np.isclose(mylocdat.z, z))

#     # test some topo polar -> cartesian 3D transformations
#     # polar args: radius phi theta
#     r = 1.0
#     print("testing LocDat 3-D polar at right temporal line")
#     mylocdat = mkh5.LocDat('electrode', 'lle',
#                             'polar', [r, 90, 0],
#                             angle_units='degrees',
#                             distance_units = 'cm')

#     assert(np.isclose(mylocdat.x, r))
#     assert(np.isclose(mylocdat.y, 0.0))
#     assert(np.isclose(mylocdat.z, 0.0))

#     print("testing LocDat 3-D polar at midline prefrontal")
#     mylocdat = mkh5.LocDat('electrode', 'lle',
#                             'polar', [r, 90, 90],
#                             angle_units='degrees',
#                             distance_units = 'cm')
#     assert(np.isclose(mylocdat.x, 0))
#     assert(np.isclose(mylocdat.y, r))
#     assert(np.isclose(mylocdat.z, 0.0))

#     print("testing LocDat 3-D polar at vertex")
#     mylocdat = mkh5.LocDat('electrode', 'lle',
#                             'polar', [r, 0, 0],
#                             angle_units='degrees',
#                             distance_units = 'cm')
#     assert(np.isclose(mylocdat.x, 0.0))
#     assert(np.isclose(mylocdat.y, 0.0))
#     assert(np.isclose(mylocdat.z, r))


# def test_load_log_eeg_event_mismatch(eeg_f='data/lm20.crw'):
#     '''test that eeg and log event codes mistmatches throw warnings'''

#     myeeg = mkh5.mkh5(eeg_f)

#     ## deliberately corrupt some eeg event codes
#     event_ptrs = (myeeg.events['eeg_evcodes'] > 0).nonzero()[0]
#     myeeg.events['eeg_evcodes'][event_ptrs[[1,3,5]]] = -37

#     log_f = re.sub('.crw$|.raw$', '.log', eeg_f)

#     print("loading log {0}".format(log_f))
#     myeeg.load_log(log_f)

#     xlog_f = re.sub('.crw$|.raw$', 'x.log', eeg_f)
#     print("loading artifact marked log {0}".format(log_f))
#     myeeg.load_log(log_f)

# def test_create_epoch(eeg_f='data/lm20.crw'):
#     myeeg = mkh5.mkh5(eeg_f)
#     my_event_stream = myeeg.events['eeg_evcodes']

#     # default is an epoch for every event in the marktrack ... lots
#     myeeg.create_epoch('bin_all', my_event_stream, 500, 2)

# def test_update_epoch(eeg_f='data/lm20.crw'):
#     myeeg = mkh5.mkh5(eeg_f)
#     my_event_stream = np.zeros_like(myeeg.events['eeg_evcodes'])
#     my_event_stream[[1000, 2000, 3000]] = 1

#     # default is an epoch for every event in the marktrack ... lots
#     myeeg.create_epoch('test_epoch', my_event_stream, 500, 2)

#     my_event_stream[[1000, 2000, 3000, 4000]] = 1
#     myeeg.update_epoch('test_epoch', my_event_stream, 500, 2)


# def test_md5(eeg_f='data/lm20.crw'):
#     ''' compare python hashlib md5 digest to openssh via system call'''
#     import subprocess
#     import binascii

#     # load up the eeg_f which includes md5 digest calculation
#     myeeg = mkh5.mkh5(eeg_f)

#     # run the linux openssl version
#     ssh_md5_str = subprocess.run(["openssl", "dgst", "-md5", eeg_f],
#                                  stdout=subprocess.PIPE).stdout.split()[1]
#     ssh_md5 = ssh_md5_str.decode('utf8')
#     print("myeeg._get_headinfo('eegmd5'): {0}".format(myeeg._get_headinfo('eegmd5')))
#     print("ssh_md5: {0}".format(ssh_md5))
#     assert myeeg._get_headinfo('eegmd5') == ssh_md5


# def test_calibration(eeg_f='data/lm20.crw'):
#     '''calibration routine with sensible default values'''

#     print("initializing with {0}".format(eeg_f))
#     myeeg = mkh5.mkh5(eeg_f)
#     log_f = re.sub('.crw$|.raw$', '.log', eeg_f)

#     print("loading log eeg_f {0}".format(log_f))
#     myeeg.load_log(log_f)

#     print("calibrating ...")
#     myeeg.calibrate(
#         n_points = 3,     # points to average on either side of cursor
#         cal_size = 10,    # uV
#         polarity = 1,     # of calibration pulse
#         lo_cursor = -30,  # ms
#         hi_cursor = 30)

#     # print("plotting cals")
#     # myeeg.plotcals()

# # FIX ME: add tests for mismatching data, cal files
