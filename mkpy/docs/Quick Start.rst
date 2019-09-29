.. _quick_start:

Quick start
===========


Single subject, single session workflow
---------------------------------------

.. code-block:: python

   from mkpy import mkh5 as mkh5

   # say which .h5 file to use and wipe it clean
   s001p3 = mkh5.mkh5('s001p3.h5')
   s001p3.reset_all()

   # load the crw, log, and YAML header
   s001p3.create_mkdata('s001', '../Data/s001p3.crw',
                                '../Data/s001p3.log',
                                's001p3.yhdr')

   # append separately recorded calibration pulses 
   s001p3.append_mkdata('s001', '../Data/s001c.crw',
                                '../Data/s001c.log',
                                's001p3.yhdr')

    # preview the cals
    pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
    f,ax = s001p3.plotcals(
        's001p3.h5', 's001',
        n_points = pts,  # pts to average, either side of cursor
        cal_size = pulse,    # uV
        lo_cursor = lo,  # lo_cursor ms
        hi_cursor = hi,  # hi_cursor ms
        cal_ccode= ccode)
    plt.show(f)

    # rescale the EEG A/D to microvolts 
    s001p3.calibrate_mkdata(
        's001',
        n_points = pts,  # pts to average, either side of cursor
        cal_size = pulse,    # uV
        lo_cursor = lo,  # lo_cursor ms
        hi_cursor = hi,  # hi_cursor ms
        cal_ccode= ccode,
        use_cals=None)

    # examine some header info
    s001p3.headinfo('dblock_0.*samplerate')
    s001p3.headinfo('hand')

    # look up event codes in the EEG data and tag with event table info
    event_table = s001p3.get_event_table('p3.xslx', 'p3.yhdx')

    # (option) process event table data epoching, e.g.,
    # convert stim-code to response-code interval from A/D samples
    # to ms for RTs and merge back in with the stim events
    srate = s001p3.gethead('dblock_0.*samplerate')[0][1]
    event_table['rt'] = event_table['anchor_tick_delta'] * (1000.0/srate)

    # store the epoch information with the data in the `mkh5` file 
    s001p3.set_epochs('p3', event_table, -100, 1000) # tmin ms, tmax ms, 

    # export the single trial epochs data as separated text, 
    # feather, or hdf5 for easy import into R, Python, or MATLAB.
    s001p3.export_epochs('p3', 's001p3.epochs.txt', file_format='txt')


Multi-subject, multi-session, workflow
-------------------------------------------

Combining data across multiple sessions within or between subjects,
experiments is exactly the same. 

The data files are simply attached to the same HDF5 file onsey-twosey
or looped in a batch.

.. code-block:: python

   from mkpy import mkh5 as mkh5

   p3h5 = mkh5.mkh5('p3.h5')
   p3h5.reset_all()

   # this is better done in a loop ...
   p3h5.create_mkdata('s001', '../Data/s001p3.crw',
                               '../Data/s001p3.log',
                               's001p3.yhdr')

   p3h5.create_mkdata('s002', '../Data/s002p3.crw',
                               '../Data/s002p3.log',
                               's002p3.yhdr')



`mkh5` continuous data
----------------------------------------

The continuous raw EEG data in HDF5 format are now available for
inspection, analysis, and sharing across computer platforms.

.. code-block:: bash

  $ h5ls -rds s001p3.h5 | head -20
  /                        Group
  /epochs                  Group
  /epochs/p3               Dataset {441}
      Data:
          (0) {"bin1", 0, nan, "10", 814, 0, 814, "s001", "s001/dblock_0", 
          (0)  0, 814, "dig", 1, "LRRL", "L", "R", "R", "L", 0, TRUE, 10, 
          (0)  10, 1, "10\000\000", 814, "s01", "runsheet", 
          (0)  "s01 09/08/17 List=h1-h2-l1-l2 Hand=LRRL", 
          (0)  "(#10)" '\000' repeats 8 times, "lo", "standard", "any\000", 
          (0)  0, -100, 1000, 789, 1064},
          (1) {"bin1", 1, nan, "10", 1082, 0, 1082, "s001", "s001/dblock_0", 
          (1)  1, 1082, "dig", 4, "LRRL", "L", "R", "R", "L", 1, TRUE, 10, 
          (1)  10, 1, "10\000\000", 1082, "s01", "runsheet", 
          (1)  "s01 09/08/17 List=h1-h2-l1-l2 Hand=LRRL", 
          (1)  "(#10)" '\000' repeats 8 times, "lo", "standard", "any\000", 
          (1)  0, -100, 1000, 1057, 1332},
          (2) {"bin1", 2, nan, "10", 1683, 0, 1683, "s001", "s001/dblock_0", 
          (2)  4, 1683, "dig", 15, "LRRL", "L", "R", "R", "L", 4, TRUE, 10, 
          (2)  10, 1, "10\000\000", 1683, "s01", "runsheet", 
          (2)  "s01 09/08/17 List=h1-h2-l1-l2 Hand=LRRL", 
          ...  



`mkh5` single trial epochs 
----------------------------------------

Single trial epochs can be exported in a data table format for import
into signal processing and statistical analysis pipelines.

.. csv-table:: 
   :file: _static/epochs_snippet.txt
   :header-rows: 1
   :delim: space




`mkh5` command cheat sheet
--------------------------

Connect
~~~~~~~
  :meth:`~mkpy.mkh5.mkh5` 
    establish a read/write connection to the ``.h5`` database file for
    subsequent operations

    
EEG data import
~~~~~~~~~~~~~~~
  :meth:`~mkpy.mkh5.mkh5.create_mkdata` 
    import a new ``.crw``, ``.log`` and additional user-specified
    header information into the database

  :meth:`~mkpy.mkh5.mkh5.append_mkdata`
    append extra data from a different ``.crw``, ``.log`` at that
    same location


Data inspection and visualization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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


Merging experimental data with EEG
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  :ref:`yhdr`
  Extend the data block headers with arbitrary experimental information when the
  ``mkh5`` EEG data are imported.

  :meth:`~mkpy.mkh5.mkh5.get_event_table`
  look up and tag single-trial event codes and event code sequences with 
  imported experimental variables in a data table format

  :ref:`yhdx`
  broadcast information from the header to a column in the event data table

  :meth:`~mkpy.mkh5.mkh5.set_epochs`
    write the single-trial tagged EEG epoch lookup table to the ``mkh5`` file


Exporting EEG and event data for analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  :meth:`~mkpy.mkh5.mkh5.export_event_table`
    write out tabular event data in tab-separated text (``.txt``) or
    feather binary data interchange format (``.fthr``).

  :meth:`~mkpy.mkh5.mkh5.export_epochs_table`
  write out tabular epochs data in tab-separated text (``.txt``) or
  feather binary data interchange format (``.fthr``).

  :meth:`~mkpy.mkh5.mkh5.export_epochs`
    write out single trial EEG data epochs defined by the epochs data
    table in the HDF5 (``.h5``) or feather (``.fthr``) binary
    data interchange formats or as tab-separated text (``.txt``)


Running ``mkpy`` on the GPU server
----------------------------------

#. Log into ``mkgpu.ucsd.edu`` with your AD credentials

#. Open a terminal window and navigate to the directory where you want
   to work.

#. At the shell prompt launch ``jupyter notebook``::

     [turbach@mkgpu1 ~]$ jupyter notebook

#. Find the jupyter window in your web browser and start a new notebook 
   or open an existing one running the ``Python 3`` kernel.

   In the first code cell enter::

     from mkpy import mkh5
     myh5 = mkh5.mkh5("some_file.h5")

#. Have at it.

