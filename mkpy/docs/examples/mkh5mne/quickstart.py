"""
Quickstart: mkh5 to MNE
#######################
"""

# %%
#
# The sample data is a single subject mkh5 data file for an auditory oddball paradigm.

# %%
# FYI ... environment and versions.
import os
import mne
import mkpy
from mkpy.io import mkh5mne

print("conda env", os.environ['CONDA_DEFAULT_ENV'])
for pkg in [mkpy, mne]:
    print(pkg.__name__, pkg.__version__)

# %%
#
# :py:func:`.mkh5mne.from_mkh5`
# =============================
#
# Import an mkh5 file into the MNE ecosystem
#
# * MNE requires electrode locations. Include them in .yhdr YAML file
#   when creating the mkh5 data or add them when converting to MNE as
#   shown here. The apparatus map format is the same.
#
# * Adding garv annotations is optional but enables the MNE automatic
#   rejection option for creating epochs.
mne_raw = mkh5mne.from_mkh5(
    "../mkh5_data/sub000p3.h5",  # file to convert
    apparatus_yaml="mne_32chan_xyz_spherical.yml",  # electrode locations
    garv_annotations={
        "event_channel": "ms1500",  # annotate events on this channel
        "start": -750,
        "stop": 750,
        "units": "ms"
    }
)

# %%
# Now run other mkh5mne functions and native MNE methods on `mne_raw`

#  mkpy.io.mkh5mne custom event finder
p3_events = mkh5mne.find_mkh5_events(mne_raw, "ms1500")

# MNE native ploting
_ = mne_raw.plot(
    p3_events,
    start=53.0,
    duration=3.0,
)
_ = mne.viz.plot_sensors(mne_raw.info)


# %%
# :py:func:`.mkh5mne.get_epochs`
# ==============================
#
# Create a native :py:class:`mne.Epochs` and attach the event
# tags from a named mkh5 epochs table as the :py:obj:`mne.Epochs.metadata`.
#
# Pass in the same arguments and key word arguments as you would for
# :py:meth:`mne.Epochs`.
mne_epochs = mkh5mne.get_epochs(
    mne_raw,
    "ms1500",
    preload=True,  # populate the Epochs with data and apply projections
    reject_by_annotation=True,  # drop the BAD_* annotations or set False to keep them
    baseline=(-0.2, 0.0)  # center on this interval
)
mne_epochs

# %%
# Gotcha: :py:meth:`mne.find_events` **IS UNSAFE**
# ================================================
# 
# .. warning::
#
#    Use mkh5 data use :py:meth:`.mkh5mne.find_mkh5_events` to create
#    MNE event arrays. **DO NOT use the native MNE**
#    :py:meth:`mne.find_events` the results may be incorrect.
#
# Various MNE raw data methods including plotting and epoching 
# ingest a 3-column `event_array` of [sample, 0, event] that says
# where (column 0) and what (column 2) the events are.
#
# The event array data format is sound and processing event
# arrays is reliable.
# 
# Unfortunately the native MNE event lookup utility
# :py:meth:`mne.find_events` for **creating** event arrays from
# event channels forcibly converts negative events to positive.
#
# Te .crw/.log/mkh5 data format routinely uses negative event codes
# for pause marks, data errors, and manually logpoked negative event
# codes. Changing the sign to positive folds them back back into the
# experimental event code range and creates creates spurious events.
# 

# %%
# How it works
# ============
#
# The sample mkh5 file is for a single subject in an auditory oddball paradigm with
# some epochs tables previously marked.
#
# Converting mkh5 HDF5 to MNE RawMkh5 does several things:
#
# * concatenates the separate mkh5 datablock EEG and event data channels into one long mne.Raw strip chart
#
# * populates the mne.Info structure with header info including
#   electrode names and locations
#
# * extracts all the mkpy epochs tables from the HDF5 and packs them into the mne.Info
#
# * for each epoch table, a new "stim" event code channel is created in the mne.Raw with
#   the name of the epochs table and all and only the events from that table.
#
# Convert the EEG and event-tagged epochs. Electrode locations are
# required, they can be included in the YAML .yhdr when the mkh5 file
# is created or added during conversion as shown.
p3_h5_f = "../mkh5_data/sub000p3.h5"
mne_raw = mkh5mne.from_mkh5(p3_h5_f, apparatus_yaml="mne_32chan_xyz_spherical.yml")

# %%
# When the mkh5 datablocks are knit together for MNE, the discontinuities at edges
# are tracked automatically as mne.Annotations
mne_raw.annotations.description

# %%
# The mne_raw object has the mne.Info attached. You can see the mkh5 epoch_table info
# peeking out of the mne.Info["description"] field.
mne_raw.info

# %%
# This RawMkh5 object can do all the usual mne.Raw tricks like plotting and writing
# itself to an MNE raw `.fif` file.
# %%
p3_events = mkh5mne.find_mkh5_events(mne_raw, "ms1500")
_ = mne_raw.plot(
    p3_events,
    start=53.0,
    duration=3.0,
)
_ = mne.viz.plot_sensors(mne_raw.info)

# %%
# Annotate garv artifacts (optional)
# ----------------------------------
#
# The mkh5 log_flags that indicate garv artifact events after ``avg
# -x`` can be converted to `BAD_garv` mne.Annotations for events on
# any of the event channels.

# Select the event channel to annotate ("log_evcodes" for all), then
# then add the annotations to the mne.Raw 
garv_bads = mkh5mne.get_garv_bads(
    mne_raw, event_channel="ms1500", start=-750, stop=750, units="ms"
)
mne_raw.set_annotations(mne_raw.annotations + garv_bads)
mne_raw.annotations

#%%
# mne.Epochs codemap metadata
# ---------------------------
#
# Use :py:meth:.`get_epochs_metadata` to extract mne.Epochs with
# the codemap metatdata 
# as MNE format metata when constructing mne.Epochs.
mne_epochs = mkh5mne.get_epochs(
    mne_raw,
    "ms1500",
    preload=True,  # populate the Epochs with data and apply projections
    reject_by_annotation=True,  # drop the BAD_* annotations or set False to keep them
    baseline=(-0.2, 0.0)  # center on this interval
)
mne_epochs

# %%
#
# The mkh5 codemap tags are attached as native mne.Epochs.metadata
mne_epochs.metadata

# %%
# :py:mod:`.mkh5mne` raw data utilities
# =====================================
#
# These utility functions access mkh5 information embedded in the RawMkH5 object.
# 
# :py:meth:`.find_mkh5_events`
# ----------------------------
#
# This is a replacement for :py:meth:`mne.find_events` that creates
# the 3 column array of [sample, 0, event] used for native mne.Raw epoching and
# plotting without doing wrong things like converting negative event
# codes to positive.
print(garv_bads, garv_bads.description)
p3_events = mkh5mne.find_mkh5_events(mne_raw, "ms1500")
p3_events

# :py:meth:`.get_find_mkh5_events`
# ----------------------------
#
# This extracts the embedded epochs table from the RawMkh5.
metadata = mkh5mne.get_epochs_metadata(mne_raw, "ms1500")
metadata
