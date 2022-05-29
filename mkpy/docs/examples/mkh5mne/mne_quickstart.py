"""
Quickstart: mkh5 to MNE
#######################
"""

# %%
#
# The sample data is a single subject mkh5 data file for an auditory oddball paradigm.

# %%
# FYI ... environment and versions. The MNE browser backend is set for generating these docs.
import os
import mne
import mkpy
from mkpy.io import mkh5mne

mne.viz.set_browser_backend("matplotlib")

print("conda env", os.environ["CONDA_DEFAULT_ENV"])
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
        "tmin": -750,
        "tmax": 750,
        "units": "ms",
    },
)

# %%
# Now run other mkh5mne functions and native MNE methods on `mne_raw`

#  mkpy.io.mkh5mne custom event finder
p3_events = mkh5mne.find_mkh5_events(mne_raw, "ms1500")

# MNE native ploting
_ = mne_raw.plot(p3_events, start=53.0, duration=3.0,)
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
    baseline=(-0.2, 0.0),  # center on this interval
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
