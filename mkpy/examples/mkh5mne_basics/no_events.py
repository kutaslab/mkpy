"""
mne.Raw without events or epochs
################################
"""
from mkpy.io import mkh5mne

# %%
# Example: Resting EEG, no events
# -------------------------------
#
# This example is resting EEG with no mkpy codemapped events or epochs tables. It
# includes data before and after scaling to :math:`\mu` V for
# demonstration, the user warnings are expected.
eeg_h5_f = "../mkh5_data/sub000eeg.h5"
eeg_raw = mkh5mne.read_raw_mkh5(eeg_h5_f)
print(eeg_raw)

# %%
eeg_raw.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4},  # scale eog and eeg channels separately
    start=282.0,  # seconds into the recording
    n_channels=39,  # EEG + event channels
)

