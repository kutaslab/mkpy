mkh5 data in MNE Python (experimental)
######################################

.. note::

  Requires mkpy >= 0.2.5 and MNE Python >=1.0 (installed by default
  when mkpy is installed with ``mamba`` or ``conda``)

An mkh5 data file can be imported into MNE Python and used with the
native MNE :py:class:`mne.Raw` continous EEG methods and
:py:class:`mne.Epochs`

Import options support automatically converting mkh5 codemapped event
tags to :py:obj:`mne.Epochs.metadata` and mkh5 garv artifacts (log_flags > 0) to
mne.Annotations for MNE native epoch artifact screening.

EEG channel and electrode location information in 3D cartesian RAS
coordinate space measured in metric units is required and provided via
a YAML file apparatus map. The apparatus map can be included as a YAML
doc in the .yhdr and baked into the mkh5 HDF5 or provided later when
the mkh5 data are converted to MNE.

The steps to prepare mkh5 data for use in MNE are as usual:

Prepare mkh5 data for MNE
=========================

For continuous EEG
------------------

1. Type up a YAML file with a mkpy standard apparatus map
   document where

   * For each channel in the `streams` map, the `pos` value
     must be a label in the `sensors` and the `mne_type` value 
     must an MNE channel type: `eeg`, `eog`, `stim`, `misc`.

   * For each electrode in the `sensors` map, give x, y, z 
     coordinates in Right Anterior Superior (RAS) space in
     the metric `units` given in the the apparatus `space` map.

2. Convert .crw/.log to mkh5 as usual.


For single trial epochs
-----------------------

3. Define an event codemap.

4. Look up the event table (:py:meth:`.mkh5.get_event_table`)

5. Set one or more named epochs tables (:py:meth:`.mkh5.set_epochs`).


Convert mkh5 to MNE
===================

For MNE continuous EEG recordings use :py:func:`.mkh5mne.from_mkh5` to create a RawMkh5 instance.

For MNE epochs :py:func:`.mkh5mne.get_epochs` on a RawMkh5 instance.

See :ref:`mkh5_with_mne` for usage and examples.


Gotcha: :py:meth:`mne.find_events` **IS UNSAFE**
================================================

.. warning::

   Use mkh5 data use :py:meth:`.mkh5mne.find_mkh5_events` to create
   MNE event arrays. **DO NOT use the native MNE**
   :py:meth:`mne.find_events` the results may be incorrect.

Various MNE raw data methods including plotting and epoching ingest a
3-column `event_array` of [sample, 0, event] that says where
(column 0) and what (column 2) the events are in the EEG recording.

The event array format is sound and processing event
arrays is reliable.

Unfortunately the native MNE event lookup utility
:py:meth:`mne.find_events` for **creating** event arrays from
event channels forcibly converts negative events to positive.

The .crw/.log/mkh5 data format routinely uses negative event codes
for pause marks, data errors, and manually logpoked negative event
codes. Changing the sign to positive folds them back back into the
experimental event code range and creates creates spurious events.


Sample YAML apparatus map
=========================

.. literalinclude:: ../examples/mkh5mne/mne_32chan_xyz_spherical.yml
   :language: yaml
