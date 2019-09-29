"""test module for primary mkh5 class methods and attributes"""

import pytest
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
    with h5py.File(h5f) as h5:
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

    mydat = mkh5.mkh5(str(h5f))
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
        mydat = mkh5.mkh5(str(h5f))
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

    myh5 = mkh5.mkh5(str(h5f))  # start fresh
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

    mydat = mkh5.mkh5(str(h5f))
    mydat.reset_all()
    mydat.create_mkdata(pfx, *GET_IRB_MKDIG(pfx))
    with h5py.File(h5f) as h5:
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
    with h5py.File(h5f) as h5:
        MiPa_after = h5[pfx + "/dblock_0"]["MiPa"]
    assert all(np.sign(MiPa_before) == np.sign(MiPa_after))
    # polarity of data heads/tails should be the same
    # pprint.pprint(mydat.info()) # visual check


@irb_data
def test_irb_calibrate_logpoked_cals():
    """test that calibration ignores logpoked cals"""

    pfx = "arquant2"
    h5f = IRB_DIR / "mkh5" / "logpoked_cals_test.h5"
    mydat = mkh5.mkh5(str(h5f))
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


# def test_load_xlog(eeg_f='data/lm20.crw'):
#     '''mkh5 avg -x artifact marked log file loader test'''
#     myeeg = mkh5.mkh5(eeg_f)
#     xlog_f = re.sub('.crw$|.raw$', '.x.log', eeg_f)


#     # this is normative usage ...
#     print("loading avg -x arked log {0}".format(xlog_f))
#     myeeg.load_log(xlog_f, presamp=500, cprecis=2)
#     print("Ok with presamp=500, cprecis=2")

#     # try/catch various fails

#     # no cprecis
#     try:
#         myeeg.load_log(xlog_f, presamp=500)
#     except ValueError:
#         print('caught no cprecis for artifact flagged log')

#     # no presamp
#     try:
#         myeeg.load_log(xlog_f, cprecis=2)
#     except ValueError:
#         print('caught no presamp for artifact flagged log')

#     # neither
#     try:
#         myeeg.load_log(xlog_f)
#     except ValueError:
#         print('caught no cprecis and presamp for artifact flagged log')


#     # main epoch not set
#     try:
#         # manually re-initialize the epoch
#         myeeg.epoch = list()

#         myeeg.load_log(xlog_f, presamp=500)
#     except ValueError:
#         print('caught main epoch not set before loading the artifact log')


# # ------------------------------------------------------------
# # h5 read tests ...
# # ------------------------------------------------------------
# def test_10cal_read_h5(h5_f='data/10cal.h5'):
#     '''mkh5 h5 short h5 reader test'''

#     # open read-only
#     with h5py.File(h5_f, 'r') as h5:
#         allgroups = []
#         h5.visit(allgroups.append)
#         for g in allgroups:
#             if isinstance(h5[g], h5py.Dataset):
#                 vals = np.array(h5[g], dtype='f4')
#                 print('{0}'.format(g))
#                 print('  head: {}'.format(vals[0:3]))
#                 print('  tail: {}'.format(vals[-3:]))
#                 print('  mean: {}'.format(np.mean(vals)), end="")
#                 print('  sd: {:5.3f}'.format(np.std(vals, ddof=1)), end="")
#                 print('  sum: {:5.3f}'.format(np.sum(vals)))

# def test_lm20_read_h5(h5_f='data/lm20.h5'):
#     '''mkh5 h5 real data reader test'''

#     # open read-only
#     with h5py.File(h5_f, 'r') as h5:
#         allgroups = []
#         h5.visit(allgroups.append)
#         for g in allgroups:
#             # print('Group: %s %s'.format(g, type(g)))
#             print('Group {0}: {1}'.format(g, type(h5[g])))
#             if isinstance(h5[g], h5py.Dataset):
#                 vals = np.array(h5[g], dtype='f4') # native eekmk f2 = float32 overflow on math ops!
#                 print('{0} length: {1:5d} mean: {2:10.5f}'.format(g, vals.size, np.mean(vals)))
#                 testvals = vals[(vals!=0).nonzero()[0]]
#                 for i in testvals[1:6]:
#                     print('{0}'.format(i), end=" ")
#                 print("\n")

# def test_10cal_write_h5(eeg_f='data/10cal.crw'):
#     '''mkh5 h5 short crw writer test'''

#     # normative usage
#     myeeg = mkh5.mkh5(eeg_f)
#     log_f = re.sub('.crw$|.raw$', '.log', eeg_f)
#     elp_f = 'data/test27.elp'

#     # myeeg.set_epoch_to(100, 1)
#     myeeg.load_log(log_f, presamp=500, cprecis=2)
#     myeeg.load_locations(elp_f, ftype='elp')
#     myeeg.calibrate(
#         n_points = 3,     # points to average on either side of cursor
#         cal_size = 10,    # uV
#         polarity = 1,     # of calibration pulse
#         lo_cursor = -30,  # ms
#         hi_cursor = 30)

#     # set h5 filename and write mode 'w' or 'r+'
#     h5_f =  re.sub('.crw$|.raw$', '.h5', eeg_f)
#     w_mode = 'w'
#     myeeg.eeg2h5(h5_f, write_mode=w_mode,
#                  compression="gzip",
#                  chunks=(2048,) )

# def test_lm20_nocal_write_h5(eeg_f='data/lm20.crw'):
#     '''squawk if trying to write uncalibrated data'''

#     # normative usage
#     myeeg = mkh5.mkh5(eeg_f)
#     xlog_f = re.sub('.crw$|.raw$', '.x.log', eeg_f)
#     myeeg.load_log(xlog_f, presamp=500, cprecis=2)

#     # hdf5 file to write
#     h5_f =  re.sub('.crw$|.raw$', '.h5', eeg_f)

#     # set mode ... 'w' write or 'r+'read/write
#     w_mode = 'w'

#     # writing before calibration should throw an error
#     try:
#         myeeg.eeg2h5(h5_f, write_mode=w_mode)
#     except Exception as msg:
#         print(msg)


# def test_lm20_write_h5(eeg_f='data/lm20.crw'):
#     '''mkh5 h5 writer test'''

#     # normative usage
#     myeeg = mkh5.mkh5(eeg_f)
#     xlog_f = re.sub('.crw$|.raw$', '.x.log', eeg_f)
#     elp_f = 'data/test27.elp'

#     # myeeg.set_epoch_to(500, 2)
#     myeeg.load_log(xlog_f, presamp=500, cprecis=2)
#     myeeg.load_locations(elp_f, ftype='elp')
#     myeeg.calibrate(
#         n_points = 3,     # points to average on either side of cursor
#         cal_size = 10,    # uV
#         polarity = 1,     # of calibration pulse
#         lo_cursor = -30,  # ms
#         hi_cursor = 30)

#     # hdf5 file to write
#     h5_f =  re.sub('.crw$|.raw$', '.h5', eeg_f)

#     # set mode ... 'w' write or 'r+'read/write
#     w_mode = 'w'

#     myeeg.eeg2h5(h5_f, write_mode=w_mode,
#                  compression="gzip",
#                  chunks=(2048,) )

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

# def test_plotcals(eeg_f='data/lm20.crw'):
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

#     print("plotting cals")
#     myeeg.plotcals()

# # FIX ME: add tests for mismatching data, cal files

# def test_load_topo(eeg_f='data/lm20.crw'):

#     log_f = re.sub('.crw$|.raw$', '.log', eeg_f)

#     print("initializing mkh5 with {0} and {1}".format(eeg_f, log_f))
#     myeeg = mkh5.mkh5(eeg_f)
#     myeeg.load_log(log_f)

#     topo_f = 'data/se64.cap'
#     print("loading topo file {0}".format(topo_f))
#     myeeg.load_locations(topo_f, 'topo')


# # ------------------------------------------------------------
# # ms <-> samples (ticks) conversion tests
# # ------------------------------------------------------------
# # intvl [opn  :    clz)[op   : clz)[opn :   clz)[opn  :   clz)
# #   ms  [-2*p : < -1*p)[-1*p : < 0)[=0  : < 1*p)[=1*p : < 2*p)
# #  samp [-2   :     -2)[-1   :  -1)[0   :     0)[1    :     1)

# # EX. sampling period p = 0.004 ms = 1.0/r for rate r

# # ------------------------------------------------------------
# # Epoching tests: backend _epoch* functions
# # ------------------------------------------------------------
# def test_get_epoch_at(eeg_f='data/lm20.crw'):
#     '''test _get_epoch_at
#     '''

#     # normative usage to load a file
#     myeeg = mkh5.mkh5(eeg_f)

#     # srate = 250
#     # cprecis = 1 -> 256 samples
#     # pause marks in lm20 [ 19455 127743 231167 259327 383999 563711 687103 836607 865535]
#     # last tick 865535
#     presamp = 100 # -> 25 samples
#     cprecis = 1
#     cp_samp = cprecis * 256  #  samples

#     # 100ms prestim = 25 samples
#     test_range = [x + 25 for x in [-2, -1, 0, 1, 2]] # sliding window

#     # these epochs underrun or overrun the data, or span a boundary
#     # the last point in epoch on a pause is allowed
#     tick_tests = [
#         # these are demos ... sequence shows transition between
#         # good and bad as the epoch slides along values in test_range
#         ('under_run',  test_range),
#         ('over_run', [myeeg.marktrack.size - (cp_samp - x) for x in test_range]), # approach and exceed last sample
#         ('start_before_boundary', [x for x in [19455, 259327, 865535] for y in test_range]), # anchor ticks on boundaries
#         ('end_after_boundary', [x + cp_samp - y for x in [19455, 259327, 865535] for y in test_range]), # anchor ticks on boundaries
#         ('anchor_equal_boundary', [19455, 259327, 865535]), # anchor ticks on boundaries

#         # these are the good tests, should all return sensible epochs (start,stop)
#         ('Go', [ x+y for x in [245, 20000] for y in test_range]),

#         # these are the bad tests, should all return (np.nan, np.nan)
#         ('NoG', [22, 23, 24] ),
#     ]

#     # for test in tick_tests:
#     #     for t in test[1]:
#     #         print('Test: {0} anchor {1}: isGo {2} isNoGo {3}'.format(
#     #             test[0], t, 'Go' in test[0], 'NoG' in test[0]))
#     # return(None)

#     for test in tick_tests:
#         for t in test[1]:
#             (start_tick, stop_tick) = myeeg._get_epoch_at(t, presamp, cprecis)
#             print('Test {0}: '.format(test[0]), end="")
#             print('anchor tick {0} presamp {1} cprecis {2} = '.format(t,presamp,cprecis), end="")
#             print("({0}, {1})".format(start_tick, stop_tick))

#             ## actual error checks
#             ## "good" tests better return sensible, non-nan epochs
#             if ('Go' in test[0]) and \
#                ( np.isnan(start_tick) or np.isnan(stop_tick) or \
#                  start_tick < 0 or stop_tick > myeeg.marktrack.size or \
#                  start_tick > t or stop_tick < t  or \
#                  ( (stop_tick - start_tick) + 1  != cp_samp ) ):

#                 errmsg="Failed Go test ... something wrong at _get_epoch_at" + \
#                     "({0},{1},{2})".format(t,presamp,cprecis) + \
#                     "= ({0},{1})".format(start_tick, stop_tick)
#                 raise ValueError(errmsg)

#             ## "bad" tests better return np.nans
#             if 'NoG' in test[0] and (not ( np.isnan(start_tick) and np.isnan(stop_tick))):
#                 errmsg="Failed NoGo test ... _get_epoch_at({0},{1},{2}) should have returned np.nan".format(t,presamp,cprecis)
#                 raise ValueError(errmsg)

# def test_get_raw_epochs(eeg_f='data/lm20.crw'):
#     '''test _get_epochs_from_eventstream
#     '''
#     # normative usage to load a file
#     myeeg = mkh5.mkh5(eeg_f)

#     # srate = 250
#     # cprecis = 1 -> 256 samples
#     # pause marks in lm20 [ 19455 127743 231167 259327 383999 563711 687103 836607 865535]
#     # last tick 865535
#     presamp = 100 # -> 25 samples
#     cprecis = 2

#     myepochs = myeeg._get_epochs_from_eventstream(myeeg.events['eeg_events'], presamp, cprecis)
#     # for x in myepochs:
#     #    print(x)

# def test_write_bin_epochs_h5():

#     eeg_f='data/lm20.crw'
#     myeeg = mkh5.mkh5(eeg_f)
#     xlog_f = re.sub('.crw$|.raw$', '.x.log', eeg_f)
#     blf_f = re.sub('.crw$|.raw$', '.blf', eeg_f)
#     elp_f = 'data/test27.elp'

#     # this is normative usage ...
#     # myeeg.set_epoch_to(500, 2)
#     myeeg.load_log(xlog_f, presamp=500, cprecis=2)

#     myeeg.calibrate(
#         n_points = 3,     # points to average on either side of cursor
#         cal_size = 10,    # uV
#         polarity = 1,     # of calibration pulse
#         lo_cursor = -30,  # ms
#         hi_cursor = 30)
#     myeeg.load_locations(elp_f, ftype='elp')
#     myeeg.load_blf(blf_f)

#     # extract the epochs to a new file
#     hdf5_f = 'data/lm20.bin.epochs.h5'
#     myeeg._write_bin_epochs_h5(hdf5_f, 'w')
