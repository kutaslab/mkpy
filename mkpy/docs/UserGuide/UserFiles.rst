.yhdr aand codemap file formats
===============================

User input files provide information in addition to the ``.crw`` and
``.log`` data.

There are three kinds:

  #. YAML format header files supplement the ``.crw`` header with
     optional recording session details, notes, subject-specific data,
     and apparatus settings including electrode locations. The .yhdr
     data is merged with with ``.crw`` and ``.log`` files when new
     data is added to the ``.h5`` file.

  #. Codemap files are used to tag event codes with experimental
     variables associated with the event, e.g., experimental
     conditions, stimulus-specific properties for stimulus events,
     responses.

  #. YAML format ``.yhdx`` header extractor formats, retrieve header
     information to merge with code mapped event information and tag event
     codes, e.g., subject, experiment, apparatus specific variables.


.. _yhdr:

YAML header files: ``.yhdr``
----------------------------

The YAML header is an open-ended mechanism for storing extra nuggets
of information with the EEG data that are useful for record keeping or
subsequent data analysis. For instance

* recording session information:
* subject variables, e.g., DOB, meds, neuropsych scores
* instrument settings, e.g., bioamp gain and filter, electrode locations



YAML header specification
~~~~~~~~~~~~~~~~~~~~~~~~~

  #. **Must** conform to YAML syntax.
  #. **Must** contain at least one YAML document, **may** contain more. 
  #. Each YAML document **must** contain the key `name` and a string label
     for a value, and **may** contain more.

.. note:: For portability between Python, MATLAB, and R all types of
   missing data should coded with the JSON value "null"
   (string). However, for use in Python/Pandas only, "null" for
   strings and .NaN for numeric data is OK and may be more efficent.

Further specifications can adopted as needed for special purposes,
e.g., importing ``mkh5`` data into other applications.

Silly Example:: 

   ## I am a minimal, legal YAML header file
   ---
   name: i_am_pointless

Slightly Less Silly Example:: 

   ## I have some genuinely useful information
   ---
   name: runsheet
   dob: 11/17/92
   adrc_id: M001A1
   mood_vas:
     pre: 4
     post: 3



.. _sample_yhdr:


Sample ``.yhdr`` (|version|)
------------------------------------

.. literalinclude:: ../../../tests/data/sample_32ch.yhdr
  :language: yaml		   



.. _yhdx:

YAML header data extractors: ``.yhdx`` 
--------------------------------------

A ``.yhdx`` YAML header extraction file is used to extract information
from the stored header so it can be included in an event table.

The format of the ``.yhdx`` is identical to the YAML header except
that in the extractor file the terminal values are replaced with
variable names that will be the column names for the extracted value

Wherever the extractor key: value path exactly matches the structure
of the header document, the data will be extracted.

The column name may but need not be the same as the key. 

For example, suppose a ``.yhdr`` YAML header file is used to inject
additional information into the ``mkh5`` data file that looks like
this:

.. code-block:: yaml

  ---
  name: runsheet
  dob: 11/17/92
  adrc_id: M001A1
  mood_vas:
    pre: 4
    post: 3


For this header, a ``.ydx`` header extractor like so

  .. code-block:: yaml

    ---
    name: runsheet

    adrc_id: adrc_id
    mood_vas:
      pre: mood_pre
      post: mood_post


pulls out this data in (wide) tabular format.

  +----------+----------+------------+
  | adrc_id  | mood_pre |  mood_post |
  +==========+==========+============+
  | M001A1   |    4     |     3      |
  +----------+----------+------------+



.. _codemap:

Event codemap files: `.xlsx`, `.ytbl`, `.txt`
---------------------------------------------

These user defined helper files contain information about how to tag
certain (sequences of) integer event codes in the data stream with
experimental design information.


Codemap specification
~~~~~~~~~~~~~~~~~~~~~

* Regardless of the file format, the codemap is always tabular: rows x
  columns.

* Two special columns control what (sequences) of codes are matched.

  1. ``regexp`` (mandatory)
       Specifies the pattern of the code sequence
       to match, at least one code, possibly flanked by others.

  2. ``ccode`` (optional)
       [New in v0.2.4] If present in the code map, the ``ccode``
       column restricts matches to data where the ``log_ccode`` in the
       HDF5 data block equals ``ccode`` in the code map. This emulates
       the familar behavior of Kutas Lab ERPSS ``cdbl`` code sequence
       pattern matching where, e.g., event code 1 with ccode==0 is a
       calibration pulse and event code 1 with ccode==1 is an
       experimental stimulus.

* The rest of the columns in the codemap are user-defined tags that
  attach to the codes that matches the pattern.  These may be for
  general information or a experimental variables factor levels, or
  numeric co-variates. There may be a few or many, though the latter
  multiply the storage requirements in RAM or on disk when processing
  time series of continuous data instead of the (typically) relatively
  small numbers of event codes.


.. warning ::
   
   Code sequence patterns are matched within each `mkh5` data block
   and cannot span data block boundaries by design.


How it works: event code sequence pattern matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Event codes are numbers and regular expressions match strings so
behind the scenes the sequence of event codes in a datablock is mapped
to a space-separated string representation. 

Example:

    log code sequence: ``[1, 1, 1, 11, 1024, 1]``

    stringified: ``' 1 1 1 11 1024 1'``


Pattern matching definitions:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

numerals
  ``0 1 2 3 4 5 6 7 8 9``

event code
    one or more numerals with or without a preceding minus
    sign.
    
    Examples: ``'1'``, ``'27'``, ``'12172'``, ``'-13864'``

code sequence
    one or more event codes separated by a single whitespace patterns
    (wild card, quantifed pattern matches)

    Example: ``'1 27 12172 -13864'``

code pattern
    a regular expression that matches a code or code sequence

    Examples: ``'1'``, ``'(12)'``, ``12\d+``, ``(1[23]\d+) 1 (1024)``

anchor pattern 
    a code pattern of the form ``(#...)`` where the ``...`` is a
    non-anchor code_pattern.

    Examples: ``'(#1)'``, ``(#12\d+)``, ``(#1[23]\d+)``, ``(#1024)``


search pattern
    a regular expression with **exactly one** anchor pattern flanked
    by **zero or more** code patterns on either side, separated by a
    single whitespace

        ``code_pattern* anchor_pattern code_pattern*``


Code map specification 
~~~~~~~~~~~~~~~~~~~~~~

In addition

* The ``regexp`` column must be a regular expression string pattern

* The remaining columns can numeric or string values with or without missing
  data **provided the values in a column all have the same data type**
        
    floating point: 17.222, 0.287, 10e27,  10e-3, etc..

    integer: -1, 0, 1, 27  10001729

    unsigned integer: 0, 1, 312, 

    boolean: True, False

    string-like: 'hi', 'hi/short', 'abra/ca/dabra'

  This is not enforced, violate at your own risk.

* missing data, None, and NaN values are supported in event tables and
  epoch table for all data types **except boolen**.

  .. Warning::

     All numeric data columns containing NaNs, None, or missing data
     missing data are converted to floating point in the epochs tables
     stored in the mkh5 data file. There are alternatives, but they
     are worse.

  NaN, None conversions as follows:
        
  +--------------+-----------------+--------------------------------+
  | Series type  |  from           | to hdf5                        |       
  +==============+=================+================================+
  | float-like   |  np.NaN, None   | np.nan                         |
  +--------------+-----------------+--------------------------------+
  | int-like     |  pd.NaN, None   | np.nan, int coerced to float\_ |
  +--------------+-----------------+--------------------------------+
  | uint-like    |  pd.NaN, None   | np.nan, int coerced to float\_ |
  +--------------+-----------------+--------------------------------+
  | string-like  |  pd.NaN, None   | b'NaN'                         |
  +--------------+-----------------+--------------------------------+
  | boolean-like |  pd.NaN, None   | not allowed                    |
  +--------------+-----------------+--------------------------------+


File types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A codemap can be any of these file types:

     Excel
       an .xlsx file and (optional) named worksheet readable by
       `pandas.DataFrame.read_excel()`

       CodeTagger('myexpt/code_tag_table.xlsx')
       CodeTagger('myexpt/code_tag_table.xlsx!for_evoked')
       CodeTagger('myexpt/code_tag_table.xlsx!for_mixed_effects')

     Tabbed text 
        a rows x columns tab-delimited text file readable by
        pandas.Data.read_csv(..., sep="\t").

     YAML
        a yaml map readable by yaml.load(), mock-tabular format
        described below.


    File formats

        Excel and Tabbed-text
            1. the data must be tabular in n rows and m columns (i,j >= 2)
            2. column labels must be in the first row
            3. the columns must includel, 'regexp', by convention the first column
            4. there must be at least one tag column, there may be more

	    +------------+--------------+------------------+
            | regexp     | col_label_1  |  <col_label_m>*  |
	    +============+==============+==================+
            | pattern_1  | code_tag_11  | <code_tag_1m>*   |
	    +------------+--------------+------------------+
            |  ...       |  ...         | ...              |
	    +------------+--------------+------------------+
            | pattern_n  | code_tag_n1  |  <datum_nm>*     |
	    +------------+--------------+------------------+

    
        YAML files
            The YAML can be any combination of inline (JSON-ic) and
            YAML indentation that PyYAML yaml.load can handle.

            1. must have one YAML document with two keys: ``columns`` and ``rows``.
            2. the first column item must be `regexp`.
            3. the columns may continue ad lib.
            4. each row must be a YAML sequence with the same number of items as there are columns

        Example

        .. code-block:: yaml

           ---
           'columns':
             [regexp, probability, frequency, source]
           'rows':
             - ['(#1)', hi,   880, oboe]
             - ['(#2)', hi,   440, oboe]
             - ['(#3)', lo,   880, oboe]
             - ['(#4)', lo,   440, oboe]
             - ['(#5)', hi,   880, tuba]
             - ['(#6)', hi,   440, tuba]
             - ['(#7)', lo,   880, tuba]
             - ['(#8)', lo,   440, tuba]

    Row value data types

    regexp :  regular expresion (`flanker* (#anchor) flanker*`)
        This is the code sequence search pattern.  Log codes are
        separated by a single whitespace for matching. The ``regexp``
        has exactly one anchor pattern capture group (# ) optionally
        flanked by zero or more code patterns.

        Flanking code patterns may capture groups (...) and
        non-capture groups (?:...)

        All matched capture event code patterns and their sample index
        (and other book-keeping info) are extracted and loaded into
        the returned code_tag_table for all capture groups.
        anchor code_pattern is always captured
            
    Additional columns: scalar (string, float, int, bool)
        this is not checked, violate at your own risk

    That's it. All the real work is done by 1) specifying
    regular expressions that match useful patterns and sequences of
    codes and 2) specifying the optional column values that label the
    matched codes in useful ways, e.g., by specifying factors and
    levels of experimental design, or numeric values for regression
    modeling or ...


Notes
~~~~~~

    * Missing data are allowed as values but discouraged b.c. 1) they
      are handled differently by the pandas csv reader vs. yaml and
      Excel readers. 2) the resulting NaNs and None coerce np.int and
      np.str dtype columns into np.object dtype and incur a
      performance penalty and 3) np.object dtypes are not readily
      serialized to hdf5 ... h5py gags and pytables pickles them. 4)
      It may lead to other unknown pathologies.

    * For yaml files, if missing values are unavoidable, coding them
      with the yaml value .NAN is recommended for all cases ... yes,
      even string data. The yaml value null maps to None and behaves
      differently in python/numpy/pandas. This is not enforced,
      violate at your own risk

    * Floating point precision. Reading code tag maps from yaml text files
      and directly from Excel .xlsx files introduces the same rounding
      errors for floating point numbers, e.g. 0.357 ->
      0.35699999999999998. Reading text files introduces a *different*
      rounding error, e.g.,0.35700000000000004.

    * There is no provision for <t:n-m> time interval constraints on
      code patterns. Maybe someday.



YAML Notes
----------

The same information can be formatted in various way, with different
tradeoffs. 

* `key`: `value` are handy when order doesn't matter.

.. code-block:: yaml

  ---
  name: runsheet
  dob: 11/17/92
  adrc_id: M001A1
  mood_vas:
    pre: 4
    post: 3

.. code-block:: yaml

  ---
  MiPf:
    pos:   MiPf
    neg:   A1
    gain:  10000
    hphz:  0.01
    lphz:  100.0


`sequences` are handy when order matters

.. code-block:: yaml

  block_order: 
    - A
    - B
    - B
    - A

They are not mutually exclusive:

Example: three ways to encode the following mixed tabular data:

  +---------+-------+------+-------+------+-------+
  |  index  | pos   |neg   |gain   | hphz | lphz  |
  +=========+=======+======+=======+======+=======+
  |  MiPf   | MiPf  | A1   | 20000 | 0.01 | 100.0 |
  +---------+-------+------+-------+------+-------+
  |  HEOG   | lle   | lhz  | 10000 | 0.01 | 100.0 |
  +---------+-------+------+-------+------+-------+

* pure nested `sequences` (YAML "flow" syntax, c.f. JSON).

.. code-block:: yaml

  table:[ [index, pos,   neg,  gain,   hphz, lphz ],
          [MiPf,  MiPf,   A1,  20000,  0.01, 100.0],
          [HEOG,  lhz,   lhz,  10000,  0.01, 100.0] ]

  Virtues: The structure of the table is obvious. Data is visually
  compact, fairly easy to read, type, and proofread.
 
  Vices: There's no way to tell column headings from data except by
  the order convention.  Departures break the processing pipeline or
  corrupt the data.

* `key`: `sequence` maps (c.f. headed .csv)
 
.. code-block:: yaml

  columns:
      [index, pos,   neg,  gain,   hphz, lphz ]
  rows:
    - [MiPf,  MiPf,   A1,  20000,  0.01, 100.0]
    - [HEOG,  lhz,   lhz,  10000,  0.01, 100.0]

  Virtues: The structure of the table is obvious, data is fairly
  compact, easy to read, type, and proofread. Columns headings
  are explicitly tagged and segregated from data.
 
  Vices: Data retrieval is by implicit index, *i*-th row of *j*-th column.

* Nested `key`: `value` maps::
 
    MiPf:
      pos:   MiPf
      neg:   A1
      gain:  10000
      hphz:  0.01
      lphz:  100.0

    HEOG:
      pos:   lhz
      neg:   rhz
      gain:  10000
      hphz:  0.01
      lphz:  100.0

  Virtues: Each data point is explicitly labeled and can be extracted
  by a unique slash-path tag: `MiPf/gain`. 

  Vices: The structure of the table is not obvious. Explicit
  `key:value` labelling increases storage overhead. Retrieval by tag is
  slow compared to retrieval by index.

.. hint:: For header data you plan to automatically extract with
       :meth:`~mkpy.mkh5.mkh5.get_event_table('some_data',
       'some_yhdx')` shallow `key:value` maps are likely the easiest
       to work with.

