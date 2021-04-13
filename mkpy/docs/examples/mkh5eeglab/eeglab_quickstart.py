"""
Quickstart: mkh5 to EEGLAB
##########################
"""

# %%
#
# The sample data is a single subject mkh5 data file for an auditory oddball paradigm.

# %%
# FYI ... environment and versions.
import os
import mne
import mkpy
from mkpy.io import mkh5eeglab

# %%
# .. note::
#
#    Converting mkh5 to EEGLAB .set requires MNE Python under the hood.

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
# * Standard mkh5 Right Anterior Superior (RAS) electrode coordinates
#   are required and rotated automatically to the EEGLAB
#   default. Include them in .yhdr YAML file when creating the mkh5
#   data or add them when converting to EEGLAB as shown here. The
#   apparatus map format is the same.
#
# * Adding `epochs_name` is optional, it adds the event tags
#   from the named epochs table to EEG.events and EEG.urevents.
#
# * Adding `garv_annotations` is optional but adds "boundary" events
#   to EEG.events and EEG.urevents
#
mkh5eeglab.mkh5_to_set(
    "../mkh5_data/sub000p3.h5",  # file to convert
    "sub000p3.set",  # eeglab file
    apparatus_yaml="ras_32chan_xyz_spherical.yml",  # electrode locations
    epochs_name="ms1500",
    garv_annotations={
        "event_channel": "ms1500",  # annotate events on this channel
        "tmin": -750,
        "tmax": 750,
        "units": "ms",
    },
)

# %%
# The .set file can be loaded in MATLAB with eeglab.
#
# To finish the conversion to EEGLAB clean up the events with and channel locations
# by running these. In the channel editor run the `Optimize head center` to automatically
# add the sphenical coordinates. Exclude non-scalp EEG data channels as needed to center
# the montage for EEGLAB plotting.
#
# .. code-block::matlab
#
#    >> EEG = eeg_checkset(EEG, 'eventconsistency')
#    >> pop_chanedit(EEG)
