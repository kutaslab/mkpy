"""
Read h5 to mne.Raw
==================
"""

# %% TL; DR use mkpy HDF5 to mne.Raw: :py:meth:`.read_raw_mkh5` to
# convert mkpy.mkh5 format HDF5 data files to mne.Raw with or without
# garv artifacts marked as "BAD_garv" annotations. To use mkpy codemap
# event tags with mne.Epochs, extract them from the converted mne.Raw
# with the mkh5mne utility :py:meth:`.get_epochs_metadata` and feed
# them as metadata when creating ``mne.Epochs(..., metadata=...)``.

# %%
# Set up
# -------
import mne
from mkpy import mkh5
from mkpy.io import mkh5mne

# to be clear ...
for pkg in [mkh5, mne]:
    print(pkg.__name__, pkg.__version__)

# %%
# 1. Review: mkh5 data file format
# --------------------------------
#
# This is mkh5 data for a single subject in an auditory oddball paradigm, here
# are the paths to the EEG data blocks in the file.

p3_h5_f = "../mkh5_data/sub000p3.h5"
p3_h5 = mkh5.mkh5(p3_h5_f)
p3_h5.dblock_paths

# %%
# The experimental events were tagged with a codemap and stored
# as named epochs tables ``mkh5.set_epochs(...)``.
p3_h5.get_epochs_table_names()

# %%
# The epochs tables have index information about where to find the
# events in the mkh5 file plus the experimental variables from
# the codemap.
p3_h5.get_epochs_table("ms1500")

#%%
# convert mkh5 to mne.Raw: :py:meth:`.read_raw_mkh5`
# --------------------------------------------------
#
# This method reads mkh5 EEG data blocks into an mkh5 variant of 
# the mne.Raw class. The converted object has all the EEG, event code tags, and
# epochs information from the mkh5 and can run the mne.Raw methods
# on it like plotting, epoching, and saving as .fif.
p3_raw = mkh5mne.read_raw_mkh5(p3_h5_f)

# %%
# The datablock and boundaries between them are automatically marked
# with mne.Annotations
# %%
p3_raw.annotations.description

# %%
# Selecting which datablocks to convert to mne.Raw
# ------------------------------------------------
#
# By default :py:meth:`.read_raw_mkh5` converts the entire mkh5 file.
# The mkh5 data groups and EEG datablocks are appended in the order
# order returned by :py:meth:`.dblock_paths` which sorts HDF5 the HDF5
# paths to data group alphabetically and preserves data block order
# within each group.
#
# An mkh5 file might have multiple subjects or experiments, if 
# you don't want to make it all one mne.Raw object, you can
#  select which data blocks to convert with ``datablock_paths=``.
# 
mkh5mne.read_raw_mkh5(
    p3_h5_f,
    dblock_paths=['sub000/dblock_0', 'sub000/dblock_1']
).annotations.description


# %%
# Marking garv artifacts in mne.Raw 
# ----------------------------------
# If you prepared the mkh5 file with the .log file log_flags set to
# track garv artifacts (``avg -x ``) you can automatically mark the garv artifacts
# in the mne.Raw with BAD_garv mne.Annotations by passing in the
# ``garv_interval=``. 

# %%
# parameters configure the plot, they don't impact the data
p3_raw.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4},
    start=10.0,
    n_channels=39
)

# .. warning::
# 
#    ``avg -x`` flags **all** event codes that fail a test. If your
#    events are closely spaced, as in RSVP, the BAD_garv annotation for events
#    you don't care about may overlap the epochs you do care about. If so
#    ``mne.Epochs(..., reject_by_annotation=True)`` will exclude the experimental event
#    that even though it is fine according to garv (its log_flag==0). To avoid
#    this use ``mne.Epochs(..., reject_by_annotation=False)`` and then select the good
#    epochs with ``mne.Epochs["log_flags==0"].copy()``
#    

#
# To mark mne.Raw with intervals around events that garv rejects
# use the ``garv_interval`` option with a start, stop, and time unit. This automatically
# updates the mne.Raw.annotations with BAD_garv spanning the rejected
# interval
p3_raw_garved = mkh5mne.read_raw_mkh5(
    p3_h5_f,
    garv_interval=(-500, 500, "ms")
)

p3_raw_garved.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4},
    start=10.0,
    n_channels=39
)


#%%
# Use mkpy codemap event tags with  mne.Epochs :py:meth:`.get_epochs_metadata`
# ---------------------------------------------------------------------------
#
# Converting mkh5 HDF5 to mne.Raw does two things:
# 
# * the mkpy epochs tables from the HDF5 
# * and builds a new "event code: channel in the mne.Raw with
# the name of the epochs table and just the events from that table.
# 
# To 
# To get mne.Epochs with the mkpy codemap tags use the :py:meth:.`get_epochs_metadata`method
# as MNE format metata when constructing mne.Epochs.
#


#%%
# This mkh5mne helper method converts garv log_flags artifact events to "BAD_garv" mne.Annotations
# for use with native MNE data screening.

garv_bads = mkh5mne.get_garv_bads(p3_raw, "ms1500", garv_interval=[-750, 750, "ms"])

print(garv_bads, garv_bads.description)


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

