# general yunk for test setup
from pathlib import Path
import sys

# so tests find sister mkpy directory before other installations
sys.path.insert(0, Path(__file__).parents[1])

import pytest
import mkpy


def TEST_DIR(fpath):
    """wrap a daughter to the test dir"""
    # return str(Path(__file__).parent / fpath)
    return Path(__file__).parent / fpath


# IRB protected data requred for testing are stored outside the repo
# in sister directory to top level mkpy

# hard coded outside of repo
IRB_DIR = Path(__file__).parents[2] / "mkpy_private"


# GLOBALS
CAL_ARGS = {
    "n_points": 3,
    "cal_size": 10,
    "lo_cursor": -50,
    "hi_cursor": 50,
    "cal_ccode": 0,
}

# general purpose output files
TEST_H5 = Path(TEST_DIR("data/test.h5"))
CALSTEST_H5 = Path(TEST_DIR("data/calstest.h5"))

# mkdig file sets for testing ... not IRB data
S01 = {
    "gid": "S01",
    "h5f": TEST_DIR("data/S01.h5"),
    "eeg_f": TEST_DIR("data/S01.crw"),
    "log_f": TEST_DIR("data/S01.log"),
    "yhdr_f": TEST_DIR("data/S01.yhdr"),
}

S05 = {
    "gid": "S05",
    "h5f": TEST_DIR("data/S05.h5"),
    "eeg_f": TEST_DIR("data/S05.crw"),
    "log_f": TEST_DIR("data/S05.log"),
    "yhdr_f": TEST_DIR("data/S05.yhdr"),
}


# pytest decorator for skipping tests on UCSD EEG data
irb_data = pytest.mark.skipif(
    not IRB_DIR.exists(),
    reason=f"UCSD IRB protected test EEG not available, skipping test",
)


def GET_IRB_MKDIG(pfx):
    # lookup crw, log, yhdr file path by prefix
    eeg_f = IRB_DIR / "mkdig/" / (pfx + ".crw")
    log_f = IRB_DIR / "mkdig/" / (pfx + ".log")
    yhdr_f = IRB_DIR / "mkdig/" / (pfx + ".yhdr")
    for f in [eeg_f, log_f, yhdr_f]:
        assert f.exists()
    return str(eeg_f), str(log_f), str(yhdr_f)


def MAKE_CALSTEST_H5():
    mydat = mkpy.mkh5.mkh5(CALSTEST_H5)
    mydat.reset_all()
    mydat.create_mkdata(S01["gid"], S01["eeg_f"], S01["log_f"], S01["yhdr_f"])
