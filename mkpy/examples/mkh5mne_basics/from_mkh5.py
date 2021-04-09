"""
Options for converting to mne.Raw
#################################
"""

# %%
# Set up
# -------
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
# mkh5 data file format in a nutshell
# ===================================
# This sample mkh5 data is for a single subject in an auditory oddball paradigm with
# previously set epoch tables.
#

p3_h5_f = "../mkh5_data/sub000p3.h5"
p3_h5 = mkh5.mkh5(p3_h5_f)

# %%
# Stimulus and response events of interest have been tagged with an mkh5 codemap and stored
# as named epochs tables ``mkh5.set_epochs(...)``. The epochs tables are whatever was deemed
# useful.
p3_h5.get_epochs_table_names()

# The epochs tables have index information about where to find the
# events in the mkh5 file, the experimental variables from
# the codemap, and the epoch discrete time interval specs, relative
# to the current mkh5 datablock.
epochs_table = p3_h5.get_epochs_table("ms1500")
epochs_table[
    [
        'epoch_id',
        'data_group', 'dblock_path',  # HDF5 data lookup info
        'log_evcodes', 'log_ccodes', 'log_flags',  # event code info
        'tone', 'stim', 'accuracy', 'acc_type',  # codemap tags
        'diti_t_0', 'diti_hop', 'diti_len'  # epoch t_0, offset, duration
    ]
]

# %%
#
# The mkh5 EEG and event channel data are stored in datablocks (HDF5
# Dataset) at the end of an HDF5 "slash" path:
p3_h5.dblock_paths


# %%
# Electrode locations
# ===================
#
# Converting mkh5 to mne.Raw **requires** an mkh5 format apparatus map
# with the coordinate space, fiducal landmarks and electrode
# locations. If the appartus map was included with the YAML .yhdr when
# the mkh5 file was created it will be used automatically.

mne_raw = mkh5mne.from_mkh5(p3_h5_f)

# %%
#
# This sample mkh5 data file was created with coordinates for an
# idealized "average" head, based on 3D digitized
# locations. Head-shaped locations are called for when working with
# realistic head geometry in MNE but they don't line up exactly with
# circular topographic maps.
_ = mne.viz.plot_sensors(mne_raw.info, sphere="auto")

# %%
#
# If original .yhdr did not include an apparatus map or a different
# set of locations is preferred, they can be specified when converting
# to MNE and used instead.
#
# This map overrides the original head-shaped electrode locations with
# spherical 3D coordinates which are unrealistic as human head
# geometry but line up neatly with circles for painting pretty 2D
# pictures.

mne_raw_a = mkh5mne.from_mkh5(
    p3_h5_f,
    apparatus_yaml="mne_32chan_xyz_spherical.yml"
)
_ = mne.viz.plot_sensors(mne_raw_a.info)


# %%
# Selecting which datablocks to convert to mne.Raw
# ================================================
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
mne_raw_b = mkh5mne.read_raw_mkh5(
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
mne_raw_c = mkh5mne.from_mkh5(
    p3_h5_f,
    garv_interval=(-500, 500, "ms")
)

mne_raw_c.plot(
    scalings={"eeg": 5e-5, "eog": 1e-4},
    start=10.0,
    n_channels=39
)

