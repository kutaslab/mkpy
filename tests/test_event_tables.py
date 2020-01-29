import re
import hashlib
import numpy as np
import pdb
import pprint
import uuid
import os
from pathlib import Path
import pytest

import pandas as pd
from .config import TEST_DIR, TEST_H5, IRB_DIR, GET_IRB_MKDIG, irb_data, mkpy
from mkpy import mkh5


@pytest.mark.parametrize("path_type", [str, Path])
@irb_data
def test_irb_load_code_map_files(path_type):

    # h5f = IRB_DIR / "mkh5" / (uuid.uuid4().hex + ".h5")
    h5group = "test2"
    h5f = IRB_DIR / "mkh5" / (h5group + "_test_load_codemap.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(h5group, *GET_IRB_MKDIG(h5group))

    # load code mappers in different formats as Path and str
    cm_ytbl = mkh5.CodeTagger(path_type(TEST_DIR("data/design2.ytbl")))
    cm_txt = mkh5.CodeTagger(path_type(TEST_DIR("data/design2.txt")))
    cm_xlsx = mkh5.CodeTagger(path_type(TEST_DIR("data/design2.xlsx")))
    cm_xlsx_named_sheet = mkh5.CodeTagger(
        path_type(TEST_DIR("data/design2.xlsx!code_map"))
    )

    # check for identity ... NB: nan == nan evaluates to False
    cms = [cm_ytbl, cm_txt, cm_xlsx, cm_xlsx_named_sheet]
    ncms = len(cms)
    for i, cm1 in enumerate(cms):
        for cm2 in cms[i + 1 :]:
            print("-" * 40)
            print("# ", cm1.cmf)
            print(cm1.code_map)
            for c in cm1.code_map.columns:
                print(c, cm1.code_map[c].dtype)

            print("# ", cm2.cmf)
            print(cm2.code_map)
            for c in cm1.code_map.columns:
                print(c, cm1.code_map[c].dtype)

            same = cm1.code_map == cm2.code_map
            # print(same)
            diffs = np.where(same == False)
            for r in range(len(diffs[0])):
                idx = diffs[0][r]
                jdx = diffs[1][r]
                print(
                    "{0}[{1},{2}] --> {3}".format(
                        cm1.cmf, idx, jdx, repr(cm1.code_map.iat[idx, jdx])
                    )
                )
                print(
                    "{0}[{1},{2}] <-- {3}".format(
                        cm2.cmf, idx, jdx, repr(cm2.code_map.iat[idx, jdx])
                    )
                )
            print()

    os.remove(h5f)


@irb_data
def test_irb_event_table():

    subid = "test2"
    h5f = IRB_DIR / "mkh5" / (subid + "_event_table.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    # mydat.create_mkdata('sub02', eeg_f, log_f, yhdr_f)
    # mydat.create_mkdata('sub03', eeg_f, log_f, yhdr_f)

    # sample code sequence pattern matches
    code_map_f = TEST_DIR("data/test2_items.xlsx!code_table")

    # Excel header slicers DEPRECATED
    # header_chooser_f = 'data/test2_items.xlsx!header_chooser'
    header_chooser_f = TEST_DIR("data/test2.yhdx")

    print("get_event_table() *WITHOUT* header extraction")
    event_table = mydat.get_event_table(code_map_f)
    print("get_event_table() *WITH* header extraction")
    event_table = mydat.get_event_table(code_map_f, header_chooser_f)
    # pprint.pprint(event_table)

    # test export event
    print("exporting event table")
    mydat.export_event_table(
        event_table, TEST_DIR("data/test_event_table.fthr"), format="feather"
    )

    mydat.export_event_table(
        event_table, TEST_DIR("data/test_event_table.txt"), format="txt"
    )

    # clean up
    os.remove(h5f)


@irb_data
def test_irb_event_table_b():
    subid = "test2"
    h5f = IRB_DIR / "mkh5" / (subid + "_event_table.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(subid, *GET_IRB_MKDIG(subid))

    # sample code sequence pattern matches
    code_map_f = TEST_DIR("data/test2b.ytbl")

    # Excel header slicers DEPRECATED
    # header_chooser_f = 'data/test2_items.xlsx!header_chooser'
    header_chooser_f = TEST_DIR("data/test2.yhdx")

    print("get_event_table() *WITHOUT* header extraction")
    event_table = mydat.get_event_table(code_map_f)
    print("get_event_table() *WITH* header extraction")
    event_table = mydat.get_event_table(code_map_f, header_chooser_f)
    # pprint.pprint(event_table)

    # test export event
    print("exporting event table")
    mydat.export_event_table(
        event_table, TEST_DIR("data/test_event_table_b.fthr")
    )

    mydat.export_event_table(
        event_table, TEST_DIR("data/test_event_table_b.txt"), format="txt"
    )

    # clean up
    os.remove(h5f)


@irb_data
def test_irb_event_table_fails():

    subid = "test2"
    h5f = IRB_DIR / "mkh5" / (subid + "_event_table.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(subid, *GET_IRB_MKDIG(subid))

    #  design4.ytbl is a well-formed code mapper file but no code
    #  matches in test2.h5

    try:
        event_table = mydat.get_event_table(TEST_DIR("data/design4.ytbl"))
    except Exception as err:
        # hard coded error message in mkh5.get_event_table
        if isinstance(err, RuntimeError) and "no events found" in str(err):
            print("Caught the no matching codes RuntimeError")
        else:
            msg = (
                "\nNo codes match the pattern so the event table is empty, "
                "expected a RuntimeError instead of this:\n"
            )
            raise RuntimeError(msg + str(err))
    os.remove(h5f)


@pytest.mark.parametrize("sheet", ["Sheet1", "Sheet2"])
def test_non_unique_event_table_index(sheet):
    """test xlsx codemap with non-unique index values, with and without ccode"""

    # name and reset the .h5 file
    sid = "sub000"
    eeg_f = TEST_DIR("data/sub000wr.crw")
    log_f = TEST_DIR("data/sub000wr.log")

    yhdr_f = TEST_DIR("data/sub000wr.yhdr")
    yhdx_f = TEST_DIR("data/wr.yhdx")

    cal_eeg_f = TEST_DIR("data/sub000c.crw")
    cal_log_f = TEST_DIR("data/sub000c.log")
    cal_yhdr_f = TEST_DIR("data/sub000c.yhdr")

    myh5 = mkh5.mkh5(TEST_H5)
    myh5.reset_all()

    # load in subject and cals
    myh5.create_mkdata(sid, eeg_f, log_f, yhdr_f)
    myh5.append_mkdata(sid, cal_eeg_f, cal_log_f, cal_yhdr_f)

    # calibrate data
    pts, pulse, lo, hi, ccode = 5, 10, -40, 40, 0
    myh5.calibrate_mkdata(
        sid,  # specific data group
        n_points=pts,  # pts to average
        cal_size=pulse,  # uV
        lo_cursor=lo,  # lo_cursor ms
        hi_cursor=hi,  # hi_cursor ms
        cal_ccode=ccode,
    )  # condition code

    # -----------------------------------------------------
    # check the event code table specs
    # -----------------------------------------------------
    code_map_f = TEST_DIR(f"data/wr_code_map.xlsx!{sheet}")
    event_table = myh5.get_event_table(code_map_f, yhdx_f)

    # use column Index to index the frame for these tests
    event_table.set_index('Index', inplace=True)

    # events: 209 cals, 144 block 1 words, 144 block 2 words
    events = {
        "Sheet1": {
            "shape": (288, 34),  # no ccode column
            "idx_n": 144,  # no cals, 144 unique words
            "word_lags_1": ["unique", "none"],
            "word_lags_2_3": ["short", "long"],
        },
        # Sheet2 has ccode column for bdf compatibility test
        "Sheet2": {
            "shape": (497, 35),  # 34 + ccode column
            "idx_n": 145,
            "ccodes_n": (209, 0, 144, 144),  # ccode 0, 1, 2, 3
            "word_lags_1": ["cal", "unique", "none"],
            "word_lags_2_3": ["cal", "short", "long"],
        },
    }

    idxs = event_table.index.unique()
    assert event_table.shape == events[sheet]["shape"]
    assert len(idxs) == events[sheet]["idx_n"]

    # count the ccodes, if any
    if "ccodes_n" in events[sheet].keys():
        for code, n_codes in enumerate(events[sheet]["ccodes_n"]):
            assert len(event_table.query("ccode == @code")) == n_codes

    for idx in idxs:
        row_slice = event_table.loc[idx]

        # widen long format series to 1-row dataframe
        if isinstance(row_slice, pd.Series):
            row_slice = pd.DataFrame(row_slice).T

        # check the anchor
        for idx, row in row_slice.iterrows():
            assert row["anchor_code"] == row["log_evcodes"]

        # spot check the word_lag rows
        if len(row_slice) == 1:
            assert row_slice["word_lag"].all() in events[sheet]["word_lags_1"]
        elif len(row_slice) in [2, 3]:
            # duplicate indices, multiple rows match, make sure the
            # the right number comes back
            assert (
                row_slice["word_lag"].all() in events[sheet]["word_lags_2_3"]
            )
        elif len(row_slice) == 209:
            assert row_slice["word_lag"].unique()[0] == "cal"
        else:
            print("{0}".format(row_slice))
            raise ValueError("something wrong with word rep event table")

    os.remove(TEST_H5)


@pytest.mark.parametrize("codemap", ["no_ccode", "with_ccode"])
def test_p3_yaml_codemap_ccode(codemap):
    """test YAML codemaps with and without ccode"""

    # name and reset the .h5 file
    sid = "sub000"
    eeg_f = TEST_DIR("data/sub000p3.crw")
    log_f = TEST_DIR("data/sub000p3.x.log")

    yhdr_f = TEST_DIR("data/sub000p3.yhdr")
    # yhdx_f = TEST_DIR("data/wr.yhdx")

    cal_eeg_f = TEST_DIR("data/sub000c.crw")
    cal_log_f = TEST_DIR("data/sub000c.log")
    cal_yhdr_f = TEST_DIR("data/sub000c.yhdr")

    myh5 = mkh5.mkh5(TEST_H5)
    myh5.reset_all()

    # load in subject and cals
    myh5.create_mkdata(sid, eeg_f, log_f, yhdr_f)
    myh5.append_mkdata(sid, cal_eeg_f, cal_log_f, cal_yhdr_f)

    # calibrate data
    pts, pulse, lo, hi, ccode = 5, 10, -40, 40, 0
    myh5.calibrate_mkdata(
        sid,  # specific data group
        n_points=pts,  # pts to average
        cal_size=pulse,  # uV
        lo_cursor=lo,  # lo_cursor ms
        hi_cursor=hi,  # hi_cursor ms
        cal_ccode=ccode,
    )  # condition code

    # ------------------------------------------------------------
    # Fetch and check events for codemaps with and without ccode
    # ------------------------------------------------------------

    events = {
        "no_ccode": {
            "event_shape": (492, 30),
            "ytbl": TEST_DIR("data/sub000p3_codemap.ytbl"),
            "bindesc_f": TEST_DIR("data/sub000p3_bindesc.txt"),
            "sha256": "8a8a156ccc532a5b8b9a3b606ba628fab2f3fc9f04bbb2e115c9206c42def9ba",
        },
        "with_ccode": {
            "event_shape": (701, 30),
            "ytbl": TEST_DIR("data/sub000p3_codemap_ccode.ytbl"),
            "bindesc_f": TEST_DIR("data/sub000p3_ccode_bindesc.txt"),
            "sha256": "fddb3e8d02f90fc3ab68383cfa8996d55fc342d2151e17d62e80bf10874ea4b7",
        },
    }

    ytbl = events[codemap]["ytbl"]
    event_table = myh5.get_event_table(ytbl).query("is_anchor == True")
    assert event_table.shape == events[codemap]["event_shape"]
    print(f"{ytbl} event_table {event_table.shape}")

    counts = pd.crosstab(
        event_table.bin, [event_table.log_flags > 0], margins=True
    )
    counts.columns = [str(col) for col in counts.columns]

    coi = ["regexp", "bin", "tone", "stim", "accuracy", "acc_type"]
    bin_desc = (
        event_table[coi]
        .drop_duplicates()
        .sort_values("bin")
        .join(counts, on="bin")
        .reset_index()
    )

    bindesc_f = events[codemap]["bindesc_f"]
    # use this to rebuild the gold standard file in event of a change
    # bin_desc.to_csv(events[codemap]["bindesc_f"], sep="\t", index=False)
    with open(bindesc_f, "rb") as bd:
        sha256 = hashlib.sha256(bd.read()).hexdigest()
        assert (
            sha256 == events[codemap]["sha256"]
        )

    assert all(bin_desc == pd.read_csv(bindesc_f, sep="\t"))
