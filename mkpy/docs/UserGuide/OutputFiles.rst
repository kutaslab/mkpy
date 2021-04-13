mkh5 EEG, events, and epochs
============================

``mkh5`` HDF5 for Kutas Lab ERPSS
----------------------------------

Time-stamped ERPSS EEG and event code data streams and auxiliary
header information are converted to ``mkh5`` format hdf5 binary data
files.

Since ``mkh5`` data files are just hdf5 files, they can be read or
dumped by hdf5 linux command line utilities (``h5ls``, ``h5dump``) or
read processed in other languages such as MATLAB (``load_hdf``) , R
(``library(rhdf5)``, ``h5ls``), or python (``import h5py``).


The contents of an ``mkh5`` file are organized much like a file system
directory except that instead of "folders" and "files", the ``mkh5``
file has :term:`"group" <HDF5 group>` and :term:`"dataset" <HDF5
dataset>` (the term "group" is native HDF5's regrettable choice of
terminology). The groups can hold further groups or datasets and form
a tree that branches from the "root" into groups and ultimately
terminates in data sets.


Data groups
~~~~~~~~~~~~~~

There are two types of data groups, non-terminal and
terminal. Non-terminal groups hold other groups, terminal groups hold
the datasets containing the EEG data blocks.


Non-terminal data groups
   These define the upper level(s) of the HDF5 tree structure and the
   organization is up to the user.

   When ``.crw/.log`` files are loaded into the ``mkh5`` file, the
   user specifies the full slashpath from the root of the ``mkh5``
   file to the hdf5 data group in the file tree structure where the
   ERPSS data will actually be stored.

   We'll call this "loading the ``.crw/.log`` into a data group", and 
   the Python looks like these examples:

   .. code-block:: python

       myh5.create_mkdata("sub01", "sub01.crw", "sub01.log", "sub01.yhdr")
       myh5.create_mkdata("expt3/sub01", "sub01.crw", "sub01.log", "sub01.yhdr")
   .. important::

      The ``.crw/.log`` data are always loaded into the last data
      group on the slashpath.

   Some example slashpaths:

   .. parsed-literal::

      sub01
      sub02
      sub03

      expt1/sub01
      expt1/sub02
      expt1/sub03

      expt1/session1/sub01
      expt1/session1/sub02

      sub01/session1
      sub01/session2
      sub01/session3

      sub01/sessions/1
      sub01/sessions/2
      sub01/sessions/3

   If the data groups along the slash path already exist in the
   ``mkh5``, the data are attached where they belong in the tree.

   If the intermediate data groups don't exist they are created on the
   fly.

   This flexibility allows users create ``mkh5`` files with different
   configurations for analyzing single subjects or multisubject
   experiments or ...?

Terminal data groups
   The last data group on a slashpath branch is the terminal data
   group. The structure of this data group is fixed by the ``mkh5``
   format specification. Immediately below the the terminal group are
   the EEG data block datasets as described next.


Datasets: dblocks
~~~~~~~~~~~~~~~~~~

In contrast to the flexibility of the data group tree, the
organization of datasets loaded into the terminal data group is fixed
by design in the ``mkh5``.

The basic data structure is the ``mkh5`` datablock or ``dblock`` for
short.

During data acquisition with ``dig`` the recording is typically
started and stopped multiple times during the experiment, sometimes by
design, sometimes to fix problems. So a single ``.crw`` and ``.log``
file typically contains multiple segments of uninterrupted recording
separated by pauses of unknown duration.

When the ``.crw/log`` data files are loaded into the ``mkh5`` file,
the EEG and log data are snipped apart at the discontinuities and each
of the continuous segments are formed into an ``mkh5`` format
datablock and stored as an hdf5 dataset daughter of the terminal data
group in the user-specified slashpath ``h5_path`` as follows:

Within each terminal ``data_group`` the `N`- 1 data blocks are 

  * named ``dblock_0``, ``dblock_1``, ... ``dblock_N`` 

  * the integer sequence preserves the order of the continuous
    segments in the the ``.crw/.log``

  * each ``dblock_i`` is stored as a **separate** hdf5 dataset, the daughter

    ``h5_path/dblock_i``

Datablock
  * a tabular array of typed columnar data streams (time=rows)

    * unsigned integer time-stamps
    * integer event codes
    * EEG data (integer A/D samples, floating point uV). 

  * headed by flexible document-structure extensible up to 64KB. In
    the Python workspace this is available as a dict; for storage in
    the `.h5` dataset attribute it is a utf-8 JSON string.

Header
  * the `mkh5`` file format uses the hdf5.Dataset Attribute to hold the
    header information

  * Header structures are python dictionaries, serialized for hdf5
    storage as JSON strings, and tucked into the hdf5 attribute so
    they travel with the datablock.

  * data block header information is collected/generated from several
    sources. Some is read from dig .crw/.log file headers, some is
    generated at runtime as the dig data is converted to mkh5
    format. Some is generated/merged in at runtime when the YAML
    header info file is processed

  * native .crw header from the info dict returned by
    mkio._read_header()

  * ``mkh5`` adds a `streams` key to the header which gives, in column
    order, a sequence of maps, where the *j*-th map gives the name,
    data type, and column index of *j*-th data block data stream.


Single-trial EEG epochs
------------------------

Once an ``mkh5`` file with data blocks of EEG data has been
constructed and the events of interest tagged with experimental
variables in the event table the data are in a handy format for
continuous EEG data analysis.

Since the analysis of data epochs containing events of interest is a
common use case and the platform may not be Python, the
:meth:`~mkpy.mkh5.mkh5.export_epochs` method is available to write out
single trial EEG data epochs in tabular format in (``.h5``) or feather
(``.fthr``) binary data interchange formats or as tab-separated text
(``.txt``).

Epochs are defined in the usual way as relative to some event of
interest that occurred while EEG data were being
recorded. Specifically, an epoch is a sample interval with a start and
stop defined relative to a `match`` code sample from the code tagger
regular expression pattern used to tag the event with the experimental
information from the code tag table and/or extracted from the header.

Each epoch contains all the columns given by the event table,
typically event code and EEG data streams, plus the experimental
variables that were merged (or a user-selected subset of these columns).

In the exported single trial data, the column ``Time`` contains
timestamps for each sample in each epoch, with the ``match`` code at
``Time`` == 0. The column ``Epoch_idx`` contains an integer index that
uniquely identifies each epoch within the exported epochs table but
**not** across tables.

The tabular single trial epochs file can be read directly into various
scientific computing environements and from there it is a few short
steps to visualization and analysis.

This 2-D single trial EEG data table allows the non-EEG experimental
variables to travel with the EEG data during analysis sample by sample
or in the aggregate.

* row slicing the epochs table on Time index == 0 gives a (sub-)table
  containing all and only the time-locking data samples where the event
  codes of interest are found. 

* epochs grouped by timestamp and averaged within group are the grand mean
  ERP waveforms.

* epochs grouped by levels of a categorical factor column and then
  timestamp are the conventional by-condition time-domain average ERP
  waveforms. 

* epochs grouped by time stamp and modeled with a linear regression
  model give regression ERPs (see, https://kutaslab.github.io/fitgrid/)

Although it is obviously inefficient to broadcast experimental
variables to every sample in the dataset, the cost is the same as
adding any other data stream time-series, e.g., another EEG or
response channel. The simplicity and familiarity of the format
together with the rich inventory of data manipulation and analytic
functions that operate on data tables/frames shortens the distance
from single trial EEG data to analysis and interpretation for a great
many types of analysis across scientific computing platforms.

.. code-block:: python

   import pandas as pd
   epochs = pd.read_hdf('exported_epochs.h5')
   print(epochs.head())
   print(epochs.tail())
   
.. literalinclude:: ../_static/epochs_head.txt


