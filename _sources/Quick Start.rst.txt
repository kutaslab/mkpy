.. _quick_start:

Quick start with ``jupyter notebook``
=====================================

#. Conda  install ``mkpy`` and ``jupyter`` and activate the environment.

#. In a terminal window navigate to the directory where you want
   to work and run::

     $ jupyter notebook

#. Open a notebook with a Python 3 kernel, and in the first code cell enter::

     import mkpy.mkh5 as mkh5
     myh5 = mkh5.mkh5("some_file.h5")

#. The ``myh5`` instance is ready to go, the data will be stored
   ``some_file.h5``, have at it.


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



Electrode locations and fiducial landmarks (optional)
-----------------------------------------------------

Electrode locations, fiducial landmarks (nasion, left and right
preauricular points), and head shape data points can be baked into the
mkpy .h5 data header by including a ``name: apparatus`` YAML document
in the ``.yhdr`` so that the location information travels with the EEG

The mkh5 standard apparatus specifies a 3D <x, y, z> cartesian
coordinate space, <right, anterior, superior> (RAS) orientation, with
measurement units of centimeters.

A minimal apparatus map has the following keys, additional keys may be
added ad lib.

.. code-block:: yaml

  ---
  # mandatory keys and values
  name: apparatus
  space:
    coordinates: cartesian
    distance_unit: cm
    orientation: ras

  # mandatory keys. RAS x, y, z values may vary
  fiducials:
    lpa:
      x: <float>
      y: <float>
      z: <float>
    nasion:
      x: <float>
      y: <float>
      z: <float>
    rpa:
      x: <float>
      y: <float>
      z: <float>

  # Number of sensors, labels, and x, y, z  values may vary
  sensors:
    label:
      x: <float>
      y: <float>
      z: <float>



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



MNE Python Reader (experimental)
--------------------------------

The mkpy .h5 data EEG, codemap tags, and 3D location information can be
converted to ``mne.Raw`` and ``mne.Epochs`` for use with the MNE
Python analysis and visualization toolbox (https://mne.tools/stable/index.html).

First, convert the .crw/.log/.yhdr to mkpy .h5 format, tag events with
a codemap, and set the corresponding fixed-interval epochs as
usual. Though not strictly required, it is generally advisable to
ensure the 3D electrode and fiducial location data travels with the
EEG by including an apparatus map in the .yhdr file.


Continous EEG
~~~~~~~~~~~~~

Read the s01.h5 mkpy format data as an mne.Raw like so:

.. code-block:: python

  from mkpy.io import mkh5mne
  s01_raw = mkh5mne.read_raw_mkh5("s01.h5")


Epochs
~~~~~~

The epochs and codemap event tags in s01.h5 are converted to
mne.Epochs with the ``mkh5mn3.get_epochs`` helper method:

.. code-block:: python

  from mkpy.io import mkh5mne
  s01_raw = mkh5mne.read_raw_mkh5("s01.h5")
  s01_epochs = mkpy.io.mkh5mne.get_epochs(s01_raw, "tagged_epochs") 


The MNE native method ``mne.Epochs(s01_raw, ...)`` also extracts
mne.Epochs from s01_raw but does not convert the original codemap tags
to mne.Epochs.metadata.


Garv EEG screening
~~~~~~~~~~~~~~~~~~

To use event-based quality control tests like ``garv`` to screen
epochs in MNE, convert them to "BAD_garv" mne.Annotations with
:meth:`mkh5mne.get_garv_bads()<mkpy.io.mkh5mne.get_garv_bads>`, then
use native MNE methods to drop "BAD" epochs.

.. code-block:: python

  from mkpy.io import mkh5mne
  s01_raw = mkh5mne.read_raw_mkh5("s01.h5")
  garv_bads = mkh5mne.get_garv_bads(
      s01_raw,
      event_channel="log_evcodes",
      garv_interval=[-500, 1500, "ms"]
  )
  
