"""
.. _eeglab_quickstart:


Quickstart: mkh5 to EEGLAB
##########################
"""

# %%
#
# Converting mkh5 to EEGLAB .set requires MNE Python under the hood.
#
# An apparatus map with standard mkh5 Right Anterior Superior (RAS)
# electrode locations is required and rotated automatically to the
# EEGLAB default coordinates. This can be included in the .yhdr YAML
# file when creating the mkh5 file or added later when converting to
# EEGLAB as shown here. The apparatus map format is the same.
#
# .. note::
#
#    The first time you load the .set file into EEGLAB clean up the EEGLAB
#    events and center the channel locations with spherical
#    coordinates. In MATLAB
#
#    .. code-block::
#
#       >> eeglab
#       >> EEG = pop_loadset('filename','sub00.set')
#       >> EEG = eeg_checkset(EEG, 'eventconsistency')
#       >> pop_chanedit(EEG)

# %%
# FYI ... environment and versions.
import os
import mne
import mkpy
from mkpy.io import mkh5eeglab, mkh5mne


print("conda env", os.environ["CONDA_DEFAULT_ENV"])
for pkg in [mkpy, mne]:
    print(pkg.__name__, pkg.__version__)

# %%
#
# :py:func:`.mkh5eeglab.mkh5_to_set`
# ==================================
#
# Convert an mkh5 **file** into an EEGLAB format .set file
#
# * Adding `epochs_name` is optional, it adds the event tags
#   from the named epochs table to EEG.events and EEG.urevents.
#
# * Adding `garv_annotations` is optional but adds "boundary" events
#   to EEG.events and EEG.urevents
#
# The sample data is a single subject mkh5 data file for an auditory oddball paradigm.

# %%
#
# Minimal export: EEG data, datablock labels and boundaries, and log event codes.
# The mkh5 file has electrode locations baked in via the YAML .yhdr
mkh5eeglab.mkh5_to_set("../mkh5_data/sub000p3.h5", "sub000p3.set")

# %%
#
# Export with alternate electrode locations
mkh5eeglab.mkh5_to_set(
    "../mkh5_data/sub000p3.h5",
    "sub000p3.set",
    apparatus_yaml="ras_32chan_xyz_spherical.yml",
)

# %%
#
# Complete export with codemap event tags from epochs table "ms1500"
# and garv annotations for those events.
mkh5eeglab.mkh5_to_set(
    "../mkh5_data/sub000p3.h5",  # file to convert
    "sub000p3.set",  # eeglab file
    apparatus_yaml="ras_32chan_xyz_spherical.yml",  # electrode locations
    epochs_name="ms1500",  # epochs table with tagged events
    garv_annotations={
        "event_channel": "ms1500",  # mark garv artifacts for tagged events
        "tmin": -750,
        "tmax": 750,
        "units": "ms",
    },
)
