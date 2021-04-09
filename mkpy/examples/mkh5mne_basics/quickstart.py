"""
Quickstart: mkh5 to mne.Raw and mne.Epochs
##########################################
"""

# %% TL; DR use mkpy HDF5 to mne.Raw: :py:meth:`.read_raw_mkh5` to
# convert mkpy.mkh5 format HDF5 data files to mne.Raw with or without
# garv artifacts marked as "BAD_garv" annotations. To use mkpy codemap
# event tags with mne.Epochs, extract them from the converted mne.Raw
# with the mkh5mne utility :py:meth:`.get_epochs_metadata` and feed
# them as metadata when creating ``mne.Epochs(..., metadata=...)``.

# %%
# Set up
# ======
import os
import mne
from mkpy import mkh5
from mkpy.io import mkh5mne

# FYI
conda_env = os.environ['CONDA_DEFAULT_ENV']
print("conda env", conda_env)
for pkg in [mkh5, mne]:
    print(pkg.__name__, pkg.__version__)

# %%
# Convert mkh5 to mne.Raw: :py:meth:`.from_mkh5`
# ==============================================
#
# The sample mkh5 file is for a single subject in an auditory oddball paradigm with
# some epochs tables previously marked.
#
# Converting mkh5 HDF5 to mne.Raw does several things:
#
# * knits mkh5 datablock EEG and event data channels into one long mne.Raw strip chart
#
# * populates the mne.Info structure with header info including
#   electrode names and locations
#
# * extracts all the mkpy epochs tables from the HDF5 and packs them into the mne.Info
#
# * for each epoch table, new "stim" event code channel is created in the mne.Raw with
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
# Marking garv artifacts in the mne.Raw
# =====================================
#
# If the mkh5 file was created after running ``avg -x`` to track garv artifacts in the .log file,
# you can paint `BAD_garv` mne.Annotations around events that garv would reject. Specify the
# event channel to select which events to annotate. The `log_evcodes` channel annotates  all events 
# in the data. A named epochs table event channel like `ms1500` annotates only the time lock events 
# for those epochs.
garv_bads = mkh5mne.get_garv_bads(
    mne_raw,
    "ms1500",  # create BAD_garv annotation for the events in this epochs table
    garv_interval=[-750, 750, "ms"]
)
print(garv_bads, garv_bads.description)

# %%
# Update the mne.Raw annotations with the new garv bad intervals so they
# can be excluded (or not) when slicing the raw into epochs.
mne_raw.set_annotations(mne_raw.annotations + garv_bads)
mne_raw.annotations

# %%
p3_events = mkh5mne.find_mkh5_events(mne_raw, "ms1500")
_ = mne_raw.plot(
    p3_events,
    start=53.0,
    duration=3.0,
)

#%%
# mne.Epochs with mkpy codemap event tags
# =======================================
#
# To get mne.Epochs with the mkpy codemap tags use the :py:meth:.`get_epochs_metadata`method
# as MNE format metata when constructing mne.Epochs.
#
