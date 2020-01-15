import re
import numpy as np
import pdb
import pprint
import uuid
import os

import pandas as pd
from .config import TEST_DIR, TEST_H5, IRB_DIR, GET_IRB_MKDIG, irb_data, mkpy
from mkpy import mkh5


@irb_data
def test_irb_load_code_map_files():

    # h5f = IRB_DIR / "mkh5" / (uuid.uuid4().hex + ".h5")
    h5group = "test2"
    h5f = IRB_DIR / "mkh5" / (h5group + "_test_load_codemap.h5")

    mydat = mkh5.mkh5(h5f)
    mydat.reset_all()  # start fresh
    mydat.create_mkdata(h5group, *GET_IRB_MKDIG(h5group))

    # load code mappers in different formats
    cm_ytbl = mkh5.CodeTagger(TEST_DIR("data/design2.ytbl"))
    cm_txt = mkh5.CodeTagger(TEST_DIR("data/design2.txt"))
    cm_xlsx = mkh5.CodeTagger(TEST_DIR("data/design2.xlsx"))
    cm_xlsx_named_sheet = mkh5.CodeTagger(
        TEST_DIR("data/design2.xlsx!code_map")
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

    fail = None
    try:
        event_table = mydat.get_event_table(TEST_DIR("data/design4.ytbl"))
    except Exception as err:
        print("Caught the no matching codes RuntimeError")
        fail = True
    if fail is None:
        msg = (
            "uh oh ... no code pattern match, so the event table "
            + "is empty. This should have raised an error."
        )
        raise RuntimeError(msg)
    os.remove(h5f)


def test_non_unique_event_table_index():

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

    code_map_f = TEST_DIR("data/WR_event_table.xlsx!Sheet1")
    event_table = myh5.get_event_table(code_map_f, yhdx_f)

    idxs = event_table.index.unique()

    assert len(idxs) == 144
    for idx in idxs:
        row_slice = event_table.loc[idx]

        # widen long format series to 1-row dataframe
        if isinstance(row_slice, pd.Series):
            row_slice = pd.DataFrame(row_slice).T

        # check the anchor
        for idx, row in row_slice.iterrows():
            assert row["anchor_code"] == row["log_evcodes"]

        if len(row_slice) == 1:
            assert row_slice["word_lag"].all() in ["unique", "none"]
        elif len(row_slice) in [2, 3]:
            # duplicate indices, multiple rows match, make sure the
            # the right number comes back
            assert row_slice["word_lag"].all() in ["short", "long"]
        else:
            print("{0}".format(row_slice))
            raise ValueError("something wrong with word rep event table")

    os.remove(TEST_H5)
