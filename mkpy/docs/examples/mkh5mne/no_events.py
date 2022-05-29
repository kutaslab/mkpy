"""
EEG without events or epochs
############################
"""
import mne
from mkpy.io import mkh5mne

print(mne.__version__)
mne.viz.set_browser_backend("matplotlib")  # for docs generation

# %%
#
# This example is a resting EEG recording with no mkpy codemapped
# events or epochs tables.
eeg_h5_f = "../mkh5_data/sub000eeg.h5"
mne_raw = mkh5mne.from_mkh5(
    eeg_h5_f, dblock_paths=["open/dblock_0", "closed/dblock_0"],
)

# %%
mne_raw.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4}, start=282.0, n_channels=39,
)
