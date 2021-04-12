import os
from pathlib import Path
import requests  # URL IO
import mne  # or else importlib error?

from .config import TEST_DIR
import mkpy.mkh5 as mkh5
from mkpy.io import mkh5mne
# from mkpy.io.mkh5mne import RawMkh5
from mkpy.io import mkh5eeglab



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


def test_mkh5_to_set():

    dblock_paths = mkh5.mkh5(TEST_EPOCHS_MKH5_FILE).dblock_paths
    mkh5raw = mkh5mne.from_mkh5(TEST_EPOCHS_MKH5_FILE, dblock_paths=dblock_paths[1:-1])
    for epochs_name in ["ms1500", None]:
        set_f = Path(DATA_DIR / f"_test_mkh5raw_to_set_{str(epochs_name)}.set")
        print(f"testing mkh5raw_to_set: {set_f}")
        mkh5eeglab.mkh5raw_to_set(mkh5raw, set_f, epochs_name=epochs_name)

    for garv_anns in [GARV_ANNOTATIONS_MS, None]:
        infix = "_".join(str(val) for val in garv_anns.values()) if garv_anns else "None"
        set_f = Path(DATA_DIR / f"_test_mkh5_to_set_garv_{infix}.set")
        print(f"testing mkh5_to_set: {set_f}")
        mkh5eeglab.mkh5_to_set(TEST_EPOCHS_MKH5_FILE, set_f, garv_annotations=garv_anns)

