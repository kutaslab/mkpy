import h5py
import numpy as np
import pdb
import pprint
import os
import warnings
import pandas as pd
from matplotlib import pyplot as plt

from .config import TEST_DIR, IRB_DIR, GET_IRB_MKDIG, CAL_ARGS, irb_data, mkpy
from mkpy import mkh5


@irb_data
def test_irb_epochs_out_of_bounds():

    subid = "test2"
    h5_f = IRB_DIR / "mkh5" / (subid + "epochs_out_of_bounds.h5")

    code_map_f = TEST_DIR("data/test2_items.xlsx!code_table")

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()  # start fresh
    myh5.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
    myh5.calibrate_mkdata(subid, **CAL_ARGS)

    event_table = myh5.get_event_table(code_map_f)
    assert event_table.shape == (120, 33)

    # out of bounds left edge
    myh5.set_epochs("oobl", event_table, -20000, 100)
    eptbl = myh5.get_epochs_table("oobl")
    oobl_epoch_idxs = [0, 7, 38, 64]  # should be excluded
    assert all([idx not in oobl_epoch_idxs for idx in eptbl["Epoch_idx"]])

    myh5.set_epochs("oobr", event_table, -100, 20000)
    eptbl = myh5.get_epochs_table("oobr")
    oobr_epoch_idxs = [1, 18, 57, 78, 84, 117]  # should be excluded
    assert all([idx not in oobr_epoch_idxs for idx in eptbl["Epoch_idx"]])

    os.remove(h5_f)


@irb_data
def test_irb_create_epochs():

    subid = "test2"
    h5_f = IRB_DIR / "mkh5" / (subid + "create_epochs.h5")

    code_map_f = TEST_DIR("data/test2_items.xlsx!code_table")

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()  # start fresh
    myh5.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    myh5.calibrate_mkdata(subid, **CAL_ARGS)

    event_table = myh5.get_event_table(code_map_f)
    myh5.set_epochs("short_epochs", event_table, -500, 1000)
    myh5.set_epochs("long_epochs", event_table, -3000, 5000)

    # test cases that should fail
    try:
        myh5.set_epochs("short_epochs", event_table, -500, 1000)
    except Exception as fail:
        print("OK ...caught exception for duplicate epoch table name")
    else:
        msg = """
        uh oh ... failed to throw exception for duplicate epoch table name
        """
        raise RuntimeError(msg)

    try:
        missing_col = [
            x for x in event_table.columns if not x == "dblock_ticks"
        ]
        myh5.set_epochs(
            "should_have_failed", event_table[missing_cols], -500, 1000
        )
    except Exception as fail:
        print("OK ... caught missing event column exception")
    else:
        msg = "uh oh ... failed to throw missing event column exception"
        raise RuntimeError(msg)
    os.remove(h5_f)


@irb_data
def test_irb_get_epochs():

    subid = "test2"
    h5_f = IRB_DIR / "mkh5" / (subid + "get_epochs.h5")

    code_map_f = TEST_DIR("data/test2_items.xlsx!code_table")

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()  # start fresh
    myh5.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    myh5.calibrate_mkdata(subid, **CAL_ARGS)

    # check the event_table -> epochs_table round trip
    event_table = myh5.get_event_table(code_map_f)
    myh5.set_epochs("epochs_short", event_table, -500, 1000)

    # fetch the table from self and check
    epochs_table = myh5.get_epochs_table("epochs_short", format="numpy")
    myh5._check_epochs_table(epochs_table)

    # look up the table by name and check
    myh5._h5_check_epochs_table_name(myh5.h5_fname, "epochs_short")

    # now the actual data epochs
    np_epochs, attrs = myh5.get_epochs("epochs_short", format="numpy")

    good_cols = ["dblock_ticks", "log_evcodes", "is_anchor", "MiPa"]
    epochs_good_cols, attrs = myh5.get_epochs(
        "epochs_short", format="numpy", columns=["dblock_ticks"]
    )

    pd_epochs, attrs = myh5.get_epochs(
        "epochs_short", format="pandas", columns=["dblock_ticks"]
    )
    os.remove(h5_f)


@irb_data
def test_irb_export_one_sub_epochs():

    subid = "test2"
    h5_f = IRB_DIR / "mkh5" / (subid + "one_sub_eeg.h5")
    epochs_pfx = IRB_DIR / "mkh5" / (subid + "one_sub_epochs")

    code_map_f = TEST_DIR("data/test2_items.xlsx!code_table")

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()  # start fresh
    myh5.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
    myh5.calibrate_mkdata(subid, **CAL_ARGS)

    event_table = myh5.get_event_table(code_map_f)

    myh5.set_epochs("epochs_short", event_table, -500, 1000)

    # print('getting epochs data as pandas.Dataframe')
    # epochs, attrs = myh5.get_epochs('epochs_short', format='pandas')
    # print('getting epochs data as numpy.ndarray')
    # epochs, attrs = myh5.get_epochs('epochs_short', format='numpy')

    for fmt, ext in [("h5", "h5"), ("feather", "fthr"), ("txt", "txt")]:
        epochs_h5_f = f"{epochs_pfx}.{ext}"
        myh5.export_epochs("epochs_short", epochs_h5_f, file_format=fmt)
        os.remove(epochs_h5_f)

    os.remove(h5_f)


@irb_data
def test_irb_export_expt_epochs():

    # this file has 32 Ss and prebuilt with 4 second epochs/epochs already set
    # h5_f = 'data/cloze_demo.h5'
    # myh5 = mkh5.mkh5(h5_f)
    # (data, specs) = myh5.get_epochs('epochs')
    # pdb.set_trace()
    warnings.warn("Full experiment epoch export test not implemented")


@irb_data
def test_irb_messy_event_table():
    """table contains utf-16, NaN and mixed string-int column data"""

    subid = "cor01"
    cor_h5_f = IRB_DIR / "mkh5" / (subid + "create_epochs.h5")

    cor_h5 = mkh5.mkh5(cor_h5_f)
    cor_h5.reset_all()  # start fresh

    pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
    cor_h5.create_mkdata(subid, *GET_IRB_MKDIG(subid))
    cor_h5.calibrate_mkdata(subid, **CAL_ARGS)

    # simple test w/ utf-8 encoding

    colname = "Text_column"

    print("testing utf-8 xlsx")
    unicode_map_f = TEST_DIR("data/unicode_test.xlsx")
    unicode_test_xlsx = cor_h5.get_event_table(unicode_map_f)

    # this should succeed
    colname = "OK_Pre-Context"
    arry = cor_h5._pd_series_to_hdf5(unicode_test_xlsx[colname])

    # this should fail
    try:
        colname = "Bad_Pre-Context"
        arry = cor_h5._pd_series_to_hdf5(unicode_test_xlsx[colname])
    except Exception as fail:
        print("caught exception")
        pass

    # print('testing utf-8 csv')
    colname = "Text_column"
    unicode_map_f = TEST_DIR("data/unicode_test.csv")
    unicode_test_csv = cor_h5.get_event_table(unicode_map_f)
    arry = cor_h5._pd_series_to_hdf5(unicode_test_csv[colname])

    # original messy
    print("testing bad utf-16 xlsx")
    cor_code_map_f = TEST_DIR("data/congorth_item.xlsx!test")
    cor_yhdx_f = TEST_DIR("data/cor01.yhdx")
    cor_event_table_a = cor_h5.get_event_table(cor_code_map_f, cor_yhdx_f)
    colname = "Pre-Context"

    try:
        cor_h5._pd_series_to_hdf5(cor_event_table_a[colname])
    except Exception as fail:
        print("caught exception")
        pass

    try:
        cor_h5.set_epochs("cor_a", cor_event_table_a, -500, 1500)
    except mkh5.mkh5.EpochsTableDataError as fail:
        msg = f"caught epochs table data error: {cor_code_map_f}[cor_a]"
        print(msg)
    else:
        raise

    # ------------------------------------------------------------
    # TO DO:
    # this used to test the fall-thru hdf5 conversion exception but
    # changing the code tagger to append code rows instead of
    # merging the pd.data frame brings along unchecked UTF-16 from .xlsx
    # so now a unicode error is raised not EpochsTableDataError

    # cor_code_map_f = 'data/forTom_CongORTH-item.xlsx!cor_code_map'
    # cor_yhdx_f = 'data/cor01.yhdx'
    # cor_event_table_b = cor_h5.get_event_table(cor_code_map_f, cor_yhdx_f)

    # try:
    #     cor_h5.set_epochs('cor_b', cor_event_table_b, -500, 1500)
    # except mkh5.mkh5.EpochsTableDataError as fail:
    #    msg = 'caught epochs table data error: ' + cor_code_map_f + '[cor_a]'
    #    print(msg)
    # else:
    #    raise
    # ------------------------------------------------------------


def test_pd_series_to_hdf5():
    import itertools as itr

    h5_f = TEST_DIR("data/series_to_hdf5_test.h5")

    # helpers
    def test_types_to_sequence(test_types, n_each=1):
        """ utility to build a list of items type

        Parameters
        ----------
        test_types : k,v dict 
           each v is a list of native python or numpy data types 
        n_each : uint
           number of repetitions of items of each dtype

        Returns
        -------
        sequence : list
           items are 1, 2, 3, ... coerced to dtypes in test_types

        """
        for i, k in enumerate(test_types.keys()):
            # iterate thru the homogenous types + missings
            sequence = []
            for ttype in test_types[k]:
                if ttype in missing:
                    sequence.extend([ttype] * n_each)
                elif ttype == str:
                    sequence.extend([ttype(str(i + 1))] * n_each)
                elif ttype == bytes:
                    sequence.extend([ttype(str(i + 1), "utf8")] * n_each)
                elif ttype == np.bytes_:
                    sequence.extend([ttype(str(i + 1), "utf8")] * n_each)
                else:
                    # make a scalar of ttype
                    sequence.extend([ttype(i + 1)] * n_each)
        return sequence

    def run_test(test_types, n_each=1):
        test_cnt, ok_cnt = 0, 0
        for label, test_type in test_types.items():
            test_dict = dict(label=test_type)
            sequence = test_types_to_sequence(test_dict, n_each=n_each)
            for n in range(1, len(sequence) + 1):
                subsets = [s for s in itr.combinations(sequence, n)]
                # print('length: ', n, '/', len(sequence)+1, ' n subsets: ', len(subsets))
                for subset in subsets:
                    dset_name = "{0}_{1}".format(label, n)
                    test_cnt += 1
                    series = pd.Series(subset, name=dset_name)
                    arry = myh5._pd_series_to_hdf5(series)
                    assert isinstance(arry, np.ndarray)
                    assert arry.dtype != "O"

                    # test the round trip
                    with h5py.File(h5_f, "w") as h5:
                        h5[dset_name] = arry
                    with h5py.File(h5_f, "r") as h5:
                        # bytes -> str
                        series_h5 = pd.Series(h5[dset_name][...])

                    failed = None
                    # test the round trip
                    # demunge string - bytes conversion ... yuck
                    if isinstance(series_h5[0], np.bytes_):
                        series_str = pd.Series(
                            [
                                s.decode("utf8") if hasattr(s, "decode") else s
                                for s in series
                            ]
                        )
                        series_h5 = pd.Series(
                            [s.decode("utf8") for s in series_h5]
                        )
                        if not all(series_str == series_h5):
                            failed = True
                    else:
                        # have to split b.c. np.isnan(str) throws TypeError and
                        # then compare element wise b.c. np.nan == np.nan -> False
                        for i in range(len(series)):
                            if not (
                                np.isnan(series[i])
                                and np.isnan(series_h5[i])
                                or series[i] == series_h5[i]
                            ):
                                failed = True
                    if failed:
                        err_msg = (
                            "series - hdf5 round trip failed on {0}"
                        ).format(series)
                        raise TypeError(err_msg)

                    # if we make it here ...
                    ok_cnt += 1
                result = result_labels[test_cnt == ok_cnt]
            if test_cnt == ok_cnt:
                print(
                    "{0:20s} {1:5d}/{2:5d} tests: {3}".format(
                        label, ok_cnt, test_cnt, result
                    )
                )
            else:
                msg = "{0:20s} {1:5d}/{2:5d} tests: {3}".format(
                    label, ok_cnt, test_cnt, result
                )
                raise RuntimeError(msg)

    # scratch ...
    # py3_scalars = [int, float, complex, str, bool]
    # np_scalars = [int_, float_, complex_, bytes_, unicode_, bool_ ]
    # pytables_scalars = [
    #     bool,  # boolean (true/false) types. Supported precisions: 8 (default) bits. #     int,   # signed integers, 8, 16, 32 (default) and 64 bits.
    #     uint,  # unsigned integers: 8, 16, 32 (default) and 64 bits.
    #     float, # 16, 32, 64 (default)
    #     complex, # 64 (32+32), 128 (64+64, default)
    #     string, # Raw string types. Supported precisions: 8-bit positive multiples.
    # ]

    h5_f = TEST_DIR("data/coltest.h5")
    myh5 = mkh5.mkh5(h5_f)
    result_labels = dict([(1, "OK"), (0, "Fail")])

    missing = [np.nan, None]
    int_like = dict(
        int_like=[int, np.int, np.int_, np.int32, np.int64]
    )  # np.int16,
    uint_like = dict(
        uint_like=[np.uint, np.uint8, np.uint64]
    )  #  # np.uint32, np.uint16,
    float_like = dict(
        float_like=[float, np.float, np.float_, np.float32, np.float64]
    )
    complex_like = dict(complex_like=[np.complex, np.complex_, np.complex128])
    str_like = dict(
        str_like=[str, bytes, np.bytes_, np.unicode_]
    )  # np.str_ == np.unicode_
    bool_like = dict(bool_like=[bool, np.bool_, np.bool8])

    n_each = 1
    print("Go tests Pass 1. homogenous scalar types")
    test_types = dict()
    for st in [
        int_like,
        uint_like,
        float_like,
        complex_like,
        str_like,
        bool_like,
    ]:
        test_types.update(st)
    run_test(test_types, n_each=n_each)

    print("Go tests pass 2. homogenous scalar types with missing data")
    test_types = dict()
    supported_missing_data_types = [
        int_like,
        uint_like,
        float_like,
        complex_like,
        str_like,
    ]
    for st in supported_missing_data_types:
        test_dict = dict()
        for k, v in st.items():
            test_dict[k] = v + missing
        test_types.update(test_dict)
    run_test(test_types, n_each=n_each)

    # ------------------------------------------------------------
    # No-Go Pass ... raise EpochsTableDataError or fail
    # ------------------------------------------------------------
    print("No-Go tests ...")
    # mixed data types are a no-no
    try:
        test_dict = dict(all=[])
        type_names = []
        for st in [float_like, str_like]:
            for k, v in st.items():
                type_names.append(k)
                test_dict["all"] = test_dict["all"] + v
        run_test(test_dict, n_each=n_each)
    except mkh5.mkh5.EpochsTableDataError as fail:
        msg = "caught epochs table data error: " + " ".join(type_names)
        print(msg)
    else:
        raise

    # booleans with missing
    try:
        type_names = []
        for st in [bool_like]:
            test_dict = dict()
            for k, v in st.items():
                type_names.append(k)
                test_dict[k] = v + missing
        run_test(test_dict, n_each=n_each)
    except mkh5.mkh5.EpochsTableDataError as fail:
        msg = "caught epochs table data error: " + " ".join(type_names)
        print(msg)
    else:
        raise

    os.remove(h5_f)
