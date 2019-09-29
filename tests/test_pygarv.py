"""Note the pygarv test decorater approach mods the class, tests in
fixture test_X can carry over to test_Y
"""

import os
import subprocess
import numpy as np
from mkpy import mkh5, pygarv
from mkpy.pygarv import PyYarf
from .config import TEST_DIR, S01


# short file w/ cal pulses
pfx = "calstest"
data_pfx = TEST_DIR("data/" + pfx)

# dig files
eeg_f = data_pfx + ".crw"
log_f = data_pfx + ".x.log"
yhdr_f = data_pfx + ".yhdr"

# mkh5 files
# yarf
yarf_f = data_pfx + ".yarf"
ytbl_f = data_pfx + ".ytbl"  # event descriptor table

pg_h5 = data_pfx + "_pg.h5"
no_pg_h5 = data_pfx + "_no_pg.h5"


def reset_h5():
    cleanup_h5()
    myh5 = mkh5.mkh5(no_pg_h5)
    myh5.reset_all()
    myh5.create_mkdata(pfx, eeg_f, log_f, yhdr_f)
    event_table = myh5.get_event_table(ytbl_f)
    myh5.set_epochs("short_epochs", event_table, -100, 1000)
    myh5.set_epochs("medium_epochs", event_table, -500, 1500)
    myh5.set_epochs("long_epochs", event_table, -3000, 3000)


def cleanup_h5():
    try:
        os.remove(pg_h5)
        os.remove(no_pg_h5)
    except Exception:
        pass


def test_reset_h5():
    reset_h5()


def test_init_no_pg():
    """ basic calling pattern on un-pygarved h5 """
    reset_h5()
    no_pg = pygarv.PyGarv(mkh5_f=no_pg_h5)
    return no_pg


def test_update_mkh5():
    #  start w/ fresh h5 data
    reset_h5()

    # work on tmp in case there is trouble ...
    tmp_f = pg_h5 + "_tmp"
    r = subprocess.run(["cp", no_pg_h5, tmp_f])

    # init
    pg = pygarv.PyGarv(mkh5_f=tmp_f)
    pg._update_tr_docs_from_yaml_f(yarf_f)  # load yarf tests
    pg._update_mkh5()  # actually mod the h5 file

    # rename the garv marked file
    r = subprocess.run(["mv", tmp_f, pg_h5])

    # PyGarv instance w/ loadable, runnable, save-able tests
    return pg


def test_init_pg():
    """ basic calling pattern on un-pygarved h5 """
    reset_h5()
    pg = pygarv.PyGarv(mkh5_f=pg_h5)
    return pg


def test_compress_result():
    """ check full dblock length result vectors are compressed
        to lists of tuples marking start,stop sample of
        failed test intervals [ (x0,x1) ... (x0,x1)
    """
    import itertools

    pg = pygarv.PyGarv(mkh5_f=no_pg_h5)

    # degenerate dblock len == 0, not typical
    result = np.zeros(shape=(0,), dtype=bool)
    fails = pg._compress_result(result)
    assert fails == []

    # smoke test all combinations of T,F up to len 8
    # eyeball check of singletons, runs in any
    # position appears ok
    for n in range(9):
        results = list(itertools.product([0, 1], repeat=n))
        for r in results:
            result = np.array(r)
            fails = pg._compress_result(result)
            # print(result)
            # print(fails)
            # print()

    cleanup_h5()


def test_update_tr_docs():
    """build pygarv.tr_docs from an h5 file with tests given as .yarf YAML"""

    # start fresh
    reset_h5()
    pg = pygarv.PyGarv(mkh5_f=no_pg_h5)
    pg.yarf_io = pygarv.PyYarf()
    yarf_docs = pg.yarf_io.read_from_yaml(TEST_DIR("data/calstest.yarf"))

    # dry run individual tests all tests individually
    for dbp_idx, dbp in enumerate(pg.mkh5.data_blocks):
        yarf_doc = yarf_docs[dbp_idx]
        for test_idx, test in enumerate(yarf_doc["tests"]):
            # default test_idx=None is to append the tests and results
            exception = pg._update_tr_docs(dbp_idx, test_idx, test)
            if exception is not None:
                raise exception

    cleanup_h5()


def test_specs():
    """ tests test spec setter/getter round trip """

    # this is a good pg
    pg = test_update_mkh5()
    # a test w/ default test params only
    ppa_ev_specs = {  # 'dblock_path': 'calstest/dblock_0',
        "tag": "ppa test",
        "stream": "MiPf",
        "threshold": 75.0,
        "prestim": 500.0,
        "poststim": 1500.0,
    }
    pg.ppa.set_specs(ppa_ev_specs)
    gotten_specs = pg.ppa.get_specs()
    for k in ppa_ev_specs.keys():
        gotten_specs[k] == ppa_ev_specs[k]

    # test with extra params
    cppadif_specs = {  # 'dblock_path': 'calstest/dblock_0',
        "tag": "ppa_diff test",
        "stream": "MiPf",
        "stream2": "lle",
        "threshold": 75.0,
        "interval": 1000.0,
    }
    cppadif_specs["stream2"] = "MiCe"
    pg.cppadif.set_specs(cppadif_specs)
    gotten_specs = pg.cppadif.get_specs()
    for k in cppadif_specs.keys():
        gotten_specs[k] == cppadif_specs[k]

    # # ------------------------------------------------------------
    # No Go tests
    # ------------------------------------------------------------

    # ensure 'test' key:value is somewhat protected
    try:
        pg.ppa["test"] = "new_name"  # fail b.c. test
    except Exception as msg:
        print("OK ...caught " + msg.__repr__())

    # this should fail b.c. extra key for ppdadif don't exist
    # in ppa
    try:
        for k, v in cppadif_specs.items():
            pg.ppa[k] = v
    except KeyError as err:
        print("OK ... caught ", err.__repr__())

    long_string = "ABCD" * (pg.ppa._max_path_len)  # this should fail
    try:
        pg.ppa.set_specs({"tag": long_string})
    except Exception as err:
        print("long string error", err.__repr__())

    # return for other test functions
    return pg


def test_catalog():

    # best case fully pygarvable
    pg = test_update_mkh5()
    specs = list()
    catalogs = list()

    # 1.
    specs.append(pg.cppa.specs)
    catalogs.append(pg._catalog)

    # 2. state after setting ppa test
    cppa_specs = {
        "tag": "cppa test",
        "stream": "MiPf",
        "threshold": 75.0,
        "interval": 1500.0,
    }
    pg.cppa.set_specs(cppa_specs)
    specs.append(pg.cppa.specs)
    catalogs.append(pg._catalog)

    # 3. state after resetting cppa test
    pg.cppa.reset()
    specs.append(pg.cppa.specs)
    catalogs.append(pg._catalog)

    # specs should change on set/reset
    assert specs[0] != specs[1]
    assert specs[0] == specs[2]

    # catalog of tests should not ... despite what pygarv -s reports
    for c in catalogs:
        for cc in catalogs:
            for k, v in c.items():
                assert c[k] == cc[k]
    del pg


def test_decode_pygarv_stream():

    reset_h5()
    pg = pygarv.PyGarv(pg_h5)
    for i, dbp in enumerate(pg.dblock_paths):
        _, dblock = pg.mkh5.get_dblock(dbp)

        tr_doc = pg.tr_docs[i]
        pygarv_stream = dblock["pygarv"]
        result, fails = pg._decode_pygarv_stream(pygarv_stream, tr_doc)
        if any(result > 0):
            pass
            # print(tr_doc)
    cleanup_h5()


def test_cleanup_h5():
    cleanup_h5()
