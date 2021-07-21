Cheat Sheet
===========


Open mkpy.mkh5 .h5 file for read/write
--------------------------------------

  :meth:`~mkpy.mkh5.mkh5` 
    establish a read/write connection to the ``.h5`` database file for
    subsequent operations

    
Load .crw/.log into a mkpy .h5 file
-----------------------------------

  :meth:`~mkpy.mkh5.mkh5.create_mkdata` 
    start a new data group with ``.crw``, ``.log`` and ``.yhdr`` extended
    header YAML data, e.g., single subject, single session EEG recordings.

  :meth:`~mkpy.mkh5.mkh5.append_mkdata`
    append ``.crw``, ``.log`` to an existing data group, e.g., to add
    separate calibration pulse .crw/.log files or combine
    split-session recordings.


Align EEG recordings with other experimental variables
------------------------------------------------------

  :ref:`yhdr`
    Extend the recorded EEG header with arbitrary data (JSON key:
    value), e.g., individual subject, session, attributes.

  :ref:`codemap`
    Tag recorded event codes with arbitrary variables based on
    event code sequence patterns, e.g., single trial item attributes.

    .. figure:: _images/codemap_cheat_sheet.png
      :scale: 25%
      :alt: codemap cheat sheet


  :ref:`yhdx`
    extract `key:value` from the HDF5 dblock headers as `column:values` in the event data table

  :meth:`~mkpy.mkh5.mkh5.get_event_table`
    look up and tag single-trial event codes and event code sequences
    with imported experimental variables in a data table format.

  :meth:`~mkpy.mkh5.mkh5.set_epochs`
    write the single-trial tagged EEG epoch lookup table to the ``mkh5`` file


Exporting EEG and event data for analysis
------------------------------------------

  :meth:`~mkpy.mkh5.mkh5.export_event_table`
    write out tabular event data in tab-separated text (``.txt``) or
    feather binary data interchange format (``.fthr``).

  :meth:`~mkpy.mkh5.mkh5.export_epochs_table`
    write out tabular epochs data in tab-separated text (``.txt``) or
    feather binary data interchange format (``.fthr``).

  :meth:`~mkpy.mkh5.mkh5.export_epochs` write out single trial EEG
    data epochs defined by the epochs data table as 1-D vectors of
    compound data types in HDF5 (``.h5``) or with ``pandas.DataFrame``
    writers to HDF5 (``.pdh5``), feather (``.fthr``) binary data
    interchange formats or as tab-separated text (``.txt``)


Data inspection and visualization
----------------------------------------
  :meth:`~mkpy.pygarv`
    :ref:`EEG data and artifact dashboard<pygarv_all_views>`

  .. figure:: _images/viewer_all_views.png
     :figwidth: 80%
     :width: 75%
     :alt: pygarv_all_views

     pygarv dashboard



  :meth:`~mkpy.mkh5.mkh5.plotcals`
    butterfly plot the single trial cal pulses that will be used to scale
    ``.crw`` A/D values to microvolts given the parameters

  .. figure:: _images/cals.png
     :figwidth: 80%
     :width: 75%
     :alt: plot_cals

     plot_cals


  :meth:`~mkpy.mkh5.mkh5.headinfo`
    report contents of datablock headers in the ``.h5`` database,
    optionally filtered by regular expression pattern match

  :meth:`~mkpy.mkh5.mkh5.info`
    report contents of datablock headers and snippets of data for all
    of the datablocks, c.f., HDF5 utility `h5ls -rds`

  :meth:`~mkpy.mkh5.mkh5.calibrate_mkdata`
    scale ``.crw`` A/D digtized EEG to microvolts


