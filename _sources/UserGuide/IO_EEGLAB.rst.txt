Export mkh5 to EEGLAB .set (experimental)
#########################################

EEGLAB .set files can be created by converting an existing mkh5 file
or from an Mkh5Raw instance in memory.


* :py:func:`.mkh5eeglab.mkh5_to_set`  converts an mkh5 file to EEGLAB .set

* :py:func:`.mkh5eeglab.mkh5raw_to_set` exports an :py:class:`.mkh5mne.Mkh5Raw` instance to EEGLAB .set

The basic export converts just the EEG and event channels, mkh5 datablock labels and
boundaries and log events.

The keyword parameters options allow exporting mkh5 codemap event tags
and garv artifact intervals.

Both approaches require electrode information and MNE Python under the hood.

For usage examples see :ref:`eeglab_quickstart`.

For a sample YAML apparatus map see :ref:`sample_yhdr`


.. note::

   The first time you load the .set file into EEGLAB, clean up the
   EEGLAB events and center the channel locations with spherical
   coordinates.

   .. code-block:matlab

   >> EEG = eeg_checkset(EEG, 'eventconsistency');
   >> pop_chanedit(EEG)


