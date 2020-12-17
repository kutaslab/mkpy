"""
MNE Python I/O
==============
"""

# %%
# Set up
# -------
import mne
from mkpy import mkh5
from mkpy.io import mkh5mne

# to be clear ...
for pkg in [mkh5, mne]:
    print(pkg.__name__, pkg.__version__)

#%%
# mne.Raw without epochs
# -------------------------------
#
# Resting EEG with no mkpy codemapped events or epochs tables. It
# includes data before and after scaling to :math:`\mu`V for
# demonstration, the user warnings are expected.

eeg_h5_f = "mkh5_data/sub000eeg.h5"
eeg_raw = mkh5mne.read_raw_mkh5(eeg_h5_f)
print(type(eeg_raw))

eeg_raw.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4},  # scale eog and eeg channels separately
    start=282.0,  # seconds into the recording
    n_channels=39,  # EEG + event channels
)

#%%
# mne.Raw with events and epochs
# ------------------------------
#
# The events in this oddball paradigm were tagged with a codemap and used
# to set epochs of different lengths.

p3_h5_f = "mkh5_data/sub000p3.h5"

# reusable plot parameters
p3_raw_kws = dict(scalings={"eeg": 5e-5, "eog": 1e-4}, start=10.0, n_channels=39)

p3_raw = mkh5mne.read_raw_mkh5(p3_h5_f)
p3_raw.plot(**p3_raw_kws)

#%%
# This mkh5mne helper method converts garv log_flags artifact events to "BAD_garv" mne.Annotations
# for use with native MNE data screening.

garv_bads = mkh5mne.get_garv_bads(p3_raw, "ms1500", garv_interval=[-750, 750, "ms"])

print(garv_bads, garv_bads.description)
