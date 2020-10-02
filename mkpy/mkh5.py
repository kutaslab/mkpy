import hashlib
import inspect
import os.path
import re
import warnings
import h5py
import json
import pprint
import yaml
import uuid
import pandas as pd
import copy
import logging
from pathlib import Path

# import dpath.util
# from . import dpath
from mkpy import dpath
import numpy as np
import matplotlib.pyplot as plt
from mkpy import mkio, pygarv, h5tools
from mkpy.codetagger import CodeTagger
from . import current_function, indent, log_exceptions

from mkpy import get_ver

__version__ = get_ver()

logging.info("Entering " + __name__)


# FIX ME: do something w/ custom exceptions
class BadChannelsError(Exception):  # from NJS, deprecated
    pass


class BadCalibrateCallError(Exception):
    pass


class DuplicateLocationLabelError(Exception):
    pass


class MightyWeenieCals(UserWarning):
    pass


class EpochSpansBoundary(UserWarning):
    pass


class LogRawEventCodeMismatch(UserWarning):
    pass


class DigRecordsNotSequential(UserWarning):
    pass


class mkh5:
    """Import and prepare ERPSS single-trial data for cross-platform analysis.

    This class provides the user API for converting compressed binary
    EEG data files into readily accessible HDF5 files.

    Parameters
    ----------
    h5_fname : str
        Path to a new or existing HDF5 file used as the database.

    """

    # BEGIN DEPRECATED dtypes
    # _utc = 'u4' # stub for time stamp in microseconds
    # _bin_num = 'u4' # 0-base numeric bin index from blf
    # END DEPRECATED dtypes
    # _chan_num = 'u4' # 0-base numeric channel index from dig header
    # _mkAD = 'i2' # kutaslab AD samples are int16
    # _art_flag = 'u2' # bit mask for bad channels 0 = good, 1 = bad

    # numpy dtypes for the data coming from dig .crw/.raw
    _evtick = "u4"  # dig crw sample counter, mis-named clk_tick in log2asci
    _evcode = "i2"  # numeric event codes from dig marktrack *AND* log
    _log_ccode = "u2"  # numeric condition code from log
    _log_flag = "u2"  # numeric condition code from log
    _mk_EEG = "f2"  # kutaslab 12-bit AD or 16 bits after calibrating
    _epoch_t = "i8"  # positive and negative samples for interval data
    _pygarv = "uint64"  # 64-bit column to track up to 64 pygarv data tests

    # white list of dig raw (*NOT LOG*) event codes for
    # splitting the .raw/.crw into mkh5 dblocks
    _dig_pause_marks = (-16384,)

    # HDF5 slashpath to where epochs tables are stashed in the mkh5 file
    EPOCH_TABLES_PATH = "_epoch_tables"

    class Mkh5Error(Exception):
        """general purposes mkh5 error"""

        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    class Mkh5CalError(Exception):
        """mkh5 calibration error"""

        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    class Mkh5FormatError(Exception):
        """raised on mkh5 format violations"""

        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    class YamlHeaderFormatError(Exception):
        """informative errors for bad yhdr YAML files"""

        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    class EpochsTableDataError(Exception):

        """raised for pd.Series data we can't or won't directly convert for HDF5

        These include mixed num-like and str-like * booleans with missing data
        """

        def __init__(self, pd_data_type, series):
            if series.name is None:
                series.name = "un_named_series"
            if series.hasnans:
                self.msg = (
                    "\npandas.Series " + series.name + " {0} data type"
                    " with missing data/NaN not supported for "
                    " epochs tables"
                ).format(pd_data_type)
            else:
                self.msg = (
                    "\npandas.Series "
                    + series.name
                    + " {0} data type not supported for"
                    " epochs tables"
                ).format(pd_data_type)
            print(self.msg)

    class HeaderIO:
        """private-ish helper class for managing mkh5 datablock header information

        mkh5 header structures are python dictionaries, serialized for
        hdf5 storage as JSON strings, and tucked into the hdf5
        attribute so they travel with the datablock.

        The dblock header holds information collected/generated from
        various sources. Some is read from dig .crw/.log file headers,
        some is generated at runtime as the dig data is converted to
        mkh5 format. Some is generated/merged in at runtime when the
        YAML YAML header info file is processed

        * native .crw header from the info dict returned by
          mkio._read_header()

        * mkh5/hdf5 info added by mkh5_read_raw_log()

          - miscellanous
          - data stream specs, 1-1 with the dblock data columns

        * supplementary information specified in a YAML format text
          file and loaded along with the ``.crw`` and ``.log`` files
          when they are converted to the dblock, HDF5 format.

        The .crw/.dig header can be extended by loading it from a YAML
        file. See _load_yhdr() docstring for specs.

        """

        class HeaderIOError(Exception):
            def __init__(self, value):
                self.value = value

            def __str__(self):
                return str(self.value)

        class YAMLClobberError(Exception):
            """raised when a YAML header file tries to overwrite an mkh5 header reserved word
            """

            def __init__(self, hio, keyword, yhdr_f=None):
                msg = "These are mkh5 header reserved words: "
                msg += " ".join([k for k in hio._mkh5_header_types.keys()])
                msg += "{0} YAML header files are not allowed to change {1}".format(
                    yhdr_f, keyword
                )

        # template for minimal mkh5 datablock header
        # These are top-level keys. The header checkers enforce these
        # keys and data types and the streams keys and data types.
        # Everything else in the header is ad lib.
        _mkh5_header_types = {
            # as returned by mkio._load_header() from the .crw/.raw
            "name": str,  # hardcoded in mkio as "dig"
            "magic": int,  # magic number from dig header
            "subdesc": str,  # header["subdes"]
            "expdesc": str,  # header["expdes"]
            "odelay": int,  # header["odelay"], # ms from trigger to stim about 8 @60Hz
            "samplerate": float,  # hz,
            "recordduration": float,  # length of each record in seconds
            "recordsize": int,  # e.g., 256  # ns * nr of samples in each data record
            "nrawrecs": int,  # number of raw records
            "nchans": int,  # : header["nchans"], # number of channels
            # set during when mkh5._read_raw_log() reads .crw, .log
            "eeg_file": str,  # .crw file name as passed to _read_raw_log
            "eeg_file_md5": str,
            "log_file": str,  # .log file name as passed to _read_raw_log
            "log_file_md5": str,
            # ('uuid_file', str),     # not implemented
            "streams": dict,  #  items are 1-1 (unordered) for dblock columns
            "h5_dataset": str,  # set upon construction to the dblock h5py.Dataset.name
        }

        # minimal stream item upon loading into .crw/.log info into a mkh5.dblock_N
        _mkh5_header_stream_types = {
            "name": str,  # dig channel name, e.g., 'lle', 'MiPf'
            "jdx": int,  # column index in dblock_N dataset, 0, 1, ...
            "source": str,  # source pfx[NNNN] where pfx = eeg|log|other, NNNN enumerates
            "dt": str,  # string np.dtype, e.g., '<f2', '<i4'
            # from mkh5._h5_update_eeg() where h5_path + dblock_id is the
        }

        def __init__(self):
            """wake up"""
            self._json_key = "json_header"  # key used to access h5py.Dataset.attrs[]
            self._header = None
            self._slicer = None

        # ------------------------------------------------------------
        # PUBLIC CRUD
        #
        #  CRU *D*: Delete not implemented
        # ------------------------------------------------------------
        @property
        def header(self):
            """expose header data like a read-only attribute"""
            return self._header

        # Create/Update
        def new(self, hdr_dict, yhdr_f):
            """merge a dictionary and dict from the YAML file into a well-formed
               mkh5 datablock header or die
            """
            self._create(hdr_dict, yhdr_f)
            self._check_header()

        # read
        def get(self, dblock):
            """load header info from dblock into self._header

            Parameters
            ----------
            dblock : h5py.Dataset 
               The HDF5 dataset whose attribute 'json_header' holds the header JSON string. 
            """
            if not isinstance(dblock, h5py.Dataset):
                raise TypeError(
                    "dblock must be an h5py.Dataset not " + dblock.__class__
                )
            assert self._json_key in dblock.attrs.keys()
            json_str = dblock.attrs[self._json_key]
            self._header = json.loads(json_str)  # decode json into the header dict
            self._check_streams(
                dblock
            )  # are header streams 1-1 with datablock columns?
            self._check_header()  # general header check

        # update
        def set(self, dblock):
            """jsonify the current self._header as value of dblock.attrs[self._json_key]

            Parameters
            ----------
            dblock : h5py.Dataset
              writeable mkh5 datablock reference
            """
            if not isinstance(dblock, h5py.Dataset):
                raise TypeError(
                    "dblock must be an h5py.Dataset not " + dblock.__class__
                )

            self._header["h5_dataset"] = dblock.name
            self._check_streams(dblock)
            self._check_header()

            # good to go ...jsonify stuff the string into the hdf5 attribute
            json_header = json.dumps(self._header)
            if len(json_header) > 2 ** 16:
                msg = (
                    "jsonified header info exceeds 64KB ... too big for hdf5 attribute"
                )
                raise ValueError(msg)
            dblock.attrs[self._json_key] = json_header

        # C *R *UD:  header content retrieval
        def set_slicer(self, slicer_f):
            """load YAML header slicer for selecting subsets of mkh5 header values

            Parameters
            ----------
            slicer_f : str
                 YAML file in mkh5 header slicer format

            Returns
            -------
            None
                side effect: sets self._slicer


            * The mkh5 header is a tree structure (dict) with branches
              that terminate in data.

            * The mkh5 header slicer is an mkh5 header subtree
              "template" that contains

              - terminating branches only
              - string labels as terminals, e.g., col_0, col_1
             
            Ex. , ['key_0', 'key_1', ... 'key_i', col_0]

            * Walking through header slicer with dpath.util.get(path)
              fetches the data value at the end of the path and we
              label it with the slicer column name like so
             
                [ (col_0, val_0), ... (col_n, val_n)]

            This converts neatly to wide tabular format

            +---------+------+----------+
            |col_0    | ...  | col_j    |
            +=========+======+==========+
            | value_1 | ...  | value_n  |
            +---------+------+----------+

            Examples

            .. code-block:: yaml

               # here is some YAML header info
               ---
               runsheet:
                 age: 22
                 SAT_math: 720
                 SAT_verbal: 680
                 handedness: L/L
                 mood_VAS: 4.5

            The YAML header slicer follows matching paths into that header 
            to pluck out the terminal data values (leafs) and (re-)label them

            .. code-block:: yaml

               # here is an extractor for the header
               ---
               runsheet:
                 mood_VAS: mood
                 handedness: fam_hand
                 age: age

            .. note:: 
               ``key:value`` order does not matter

            This next slicer specifies the same **paths** into the
            header tree and extracts exactly the same **values**

            .. code-block:: yaml

               ---
               runsheet:
                 age: age
                 handedness: fam_hand
                 mood_VAS: mood

            The slicer paths are the same for both:

              runsheet/mood_VAS/mood

              runsheet/handedness/fam_hand  

              runsheet/age/age  
            
            Algorithm

            * HeaderIO.get_slices() extracts the header values at the end of the path, i.e.,
              22, L/L, 4.5 and pairs each datum with its path-matching slicer label like so

                [ (sub_age, 22), (fam_hand, 'L/L') ]

            * mkh5.get_event_table() converts these to wide-format and
              merges them with the rest of the single trial event code
              column information it gets from the code tag mapper.

               sub_age fam_hand
               22      'L/L'

            """
            self._slicer_f = slicer_f
            self._slicer = self._load_yaml_slicer(slicer_f)
            return None

        def _load_xlsx_slicer(self, slicer_f):
            """load code slicer from Excel .xlsx file and return pandas
            DataFrame. Default is first sheet, use slicer_f!sheet_name
            to select sheet_name
            """
            slicer = None
            # if a sheet is specified w/ slicer!sheet use it, otherwise
            # set to 0 for default first sheet
            slicer_f_reob = re.match(
                r"(?P<xl_f>.+\.xls[xm])[\!]*(?P<sheet_name>.*)$", slicer_f
            )
            xl_f = slicer_f_reob["xl_f"]
            sheet_name = slicer_f_reob["sheet_name"]
            if len(sheet_name) == 0:
                sheet_name = 0

            slicer = pd.read_excel(
                xl_f, sheet_name=sheet_name, header=0  # , index_col="Index"
            )

            if slicer is not None:
                return slicer

        def _load_txt_slicer(self, slicer_f):
            """load tab-separated UTF-8 text file and return pandas DataFrame"""
            raise NotImplemented
            with open(slicer_f, "r") as d:
                mapper = pd.read_table(
                    slicer_f, delimiter="\t", header=0  # , index_col="Index"
                )
            return mapper

        def _load_yaml_slicer(self, slicer_f):
            """load yaml mapper file and return pandas DataFrame"""

            # slurp the slicer
            slicer_dict, hdocs, md5 = self._load_yaml_docs(slicer_f)
            slicers = []
            slicer_paths = [
                dpath.path.paths_only(x)
                for x in dpath.path.paths(slicer_dict, dirs=False, leaves=True)
            ]
            for path in slicer_paths:
                slicers.append((path[-1], path[:-1]))
            slicers = dict(slicers)
            return slicers

        def get_slices(self):
            """slice out data values from dblock header for use in event table columns

            Parameters
            ----------
            slicer : dict
               dictionary of col_name: slash_pattern where,
               * col_name (string) is the dict key that will appear as a table column heading
               * search_path (list of strings) as [ 'key1', 'key2', ... key_n] to probe header

            Returns
            -------
            slicer : list of 2-ples, possibly empty)
                each tuple is (col_name, datum) where
            datum : object
                leaf returned by dpath.util.get(self._header, search_path)

            Raises
            ------
            RuntimeError if HeaderIO instance doesn't have self._header or self._slicer dicts
            RuntimeError if dpath.util.get finds multiple values
            """

            if self._header is None or not isinstance(self._header, dict):
                msg = (
                    "load header from a datablock with HeaderIO.get(dblock) "
                    "before slicing"
                )
                raise RuntimeError(msg)

            if self._slicer is None or not isinstance(self._slicer, dict):
                msg = (
                    "set self._slicer = HeaderIO._load_yaml_docs(yaml_f) "
                    "before slicing"
                )
                raise RuntimeError(msg)

            slices = list()
            hdr_paths = [
                p for p in dpath.path.paths(self._header, dirs=False, leaves=False)
            ]
            for k, v in self._slicer.items():
                this_slice = None
                try:
                    datum = dpath.util.get(self._header, v)
                    this_slice = (k, datum)
                except Exception as fail:
                    if isinstance(fail, KeyError):
                        this_slice = (k, float("NaN"))  # key not found
                    elif isinstance(
                        fail, ValueError
                    ):  # multiple values ... shouldn't happen
                        msg = "mutiple leaves match dpath glob ... but how?"
                        raise ValueError(msg)
                    else:
                        print("some horrible error in HeaderIO.get_slices()")
                        raise fail
                slices.append(this_slice)
            return slices  # possibly empty

        # ------------------------------------------------------------
        # PRIVATE-ish CRUD
        # ------------------------------------------------------------
        # this is the only way to form an mkh5 header dict ... seed_dict + YAML
        def _create(self, seed_dict, yhdr_f):
            """merges seed_dict ON TOP of the YAML and set self._header"""

            # yhdr_f Path should be stringified by mkh5.create_mkdata
            if not isinstance(yhdr_f, str):
                raise HeaderIOError(
                    f"please report mkpy bug: {yhdr_f} must be a str not {type(yhdr_f)}"
                )

            if not isinstance(seed_dict, dict):
                msg = "seed_dict is not a dict"
                raise TypeError(msg)
            self._header = seed_dict

            # mkh5 headers know about the h5_path/block_id but
            # dicts pulled from .crw headers don't, so add a stub
            for k in ["name", "h5_dataset"]:
                if k not in seed_dict:
                    self._header[k] = ""

            # load YAML info and merge it in
            yhdr = self._load_yhdr(yhdr_f)
            assert isinstance(yhdr, dict)
            self._update_from_dict(yhdr, keep_existing=True)
            self._check_header()

        def _update_from_dict(self, new_dict, keep_existing=True):
            """Update current header dictionary from other dictionary.

            Parameters
            ----------
            keep_existing : bool, default is True
                ``True`` protects self._header[k] from being overwritten
                by new_dict[k]. ``False`` allows ``new_dict[k]`` to overwrite
                ``self._header[k]``

            Notes
            -----
            dpath.util.merge(A,B) merges B **ON TOP** of A, so
            B[key]:value sets (overwrites) A[key]:value.

            """
            self._check_header()

            if keep_existing:
                # merge existing on top of the new to preserve existing
                dpath.util.merge(new_dict, self._header)
                self._header = copy.deepcopy(new_dict)
            else:
                # merge new on top of existing to clobber the new
                dpath.util.merge(self._header, new_dict)
                self._header = copy.deepcopy(self._header)

            self._check_header()

        def _update_from_slashpaths(self, slash_vals):
            """ header date via dpath (slash_path:value) syntax

            Parameters:

            slash_vals (slashpath, value) 2ple or iteratble of them
            """
            self._check_header()
            for sv in slash_vals:
                # gate keeper
                if not (
                    isinstance(sv, tuple) and len(sv) == 2 and isinstance(sv[0], str)
                ):
                    msg = (
                        "to set header with slashpath use a ('slash/path', value) 2-ple"
                        + " or a list of them"
                    )
                    raise TypeError(msg)

                # FIX ME: protect reserved keys??
                old_val = dpath.util.search(self._header, sv[0])
                if len(old_val) == 0 and isinstance(old_val, dict):
                    # print('new key:value ', sv[0], sv[1])
                    dpath.util.new(self._header, sv[0], sv[1])
                else:
                    # print('setting existing key ', sv[0], 'old: ', old_val, 'new: ', sv[1])
                    nset = dpath.util.set(self._header, sv[0], sv[1])
                    if nset is None:
                        raise RuntimeError("failed to set " + sv[0] + " = " + sv[1])
            self._check_header()

        def _load_yaml_docs(self, yml_f):
            """generic multi-doc YAML loader for header data and extractor files"""

            # FIX ME: add YAML linter
            # check for legal yaml
            with open(yml_f, "r") as f:
                yml_str = f.read()
                hdocs = yaml.load_all(yml_str, Loader=yaml.SafeLoader)
                yml_f_md5 = hashlib.md5(yml_str.encode("utf8")).hexdigest()

            # load up the docs w/ modicum of error checking
            yml = dict()
            doc_names = []  #
            for i, hdoc in enumerate(hdocs):
                if hdoc is None:
                    msg = "uh oh ... empty YAML document in "
                    msg += "{0} perhaps a stray ---".format(yml_f)
                    raise mkh5.YamlHeaderFormatError(msg)

                if "name" not in hdoc.keys():
                    msg = "\n{0}\n".format(self._load_yaml_docs.__doc__)
                    msg += "{0} document {1} does not have a name".format(yml_f, i)
                    raise mkh5.YamlHeaderFormatError(msg)

                if len(hdoc["name"]) == 0:
                    msg = "{0} document {1}: length of name appears to be 0".format(
                        yml_f, i
                    )
                    raise mkh5.YamlHeaderFormatError(msg)

                if hdoc["name"] in doc_names:
                    msg = "{0} duplicate document name {1}".format(yml_f, hdoc["name"])
                    raise mkh5.YamlHeaderFormatError(msg)

                else:
                    # the "dig" keys are not nested under the document name
                    if hdoc["name"] == "dig":
                        dpath.util.merge(yml, hdoc)
                    else:
                        doc_names.append(hdoc["name"])
                        yml[hdoc["name"]] = hdoc

            return (yml, doc_names, yml_f_md5)

        def _load_yhdr(self, yhdr_f):
            """load a YAML format header extension
            
            Syntax: 
  
            * Must conform to YAML spec (?2.0)

            * There MUST be at least one YAML document

            * EACH YAML docs must contain a ``name`` key and string
              value

            OPTIONAL
             
            * Additional YAML documents may be added to the file ad lib provided
              each document is named with a key-value pair like so

                ---
                name: doc_name

              where doc_name is a string and not used for any other
              document in the file.

            * Additional YAML data may be specified ad lib. to extend
              any document or data.


            * Apparatus doc is a fixed-format map with these keys and
              values
        
                 name: "apparatus"
                 space: 
                 fiducial: 
                 sensor: 
                 stream: 


             The ``fiducial``, ``sensor``, and ``stream`` data are
             each given as 2-level maps where the top level key gives
             the "name", e.g., lle, MiPf, HEOG, nasion and the nested
             key:value pairs give the value of the key, e.g., gain:
             10000 for an amplifier channel or x: 18.9 for 3D
             coordinate x. This affords easy conversion to tabular
             format where top level keys index rows and, nested keys
             are column labels, and nested values are column data.

             * fiducial must contain top-level keys "nasion", "lpa",
               "rpa" and nested keys x, y, z

             * sensor must contain top-level keys naming electrodes,
               e.g. lle, MiPf and nested keys x, y, z

             * stream must contain top-level keys naming digital data
               channels, e.g., lle, MiPf, HEOG (note these are
               recordings/data streams *NOT* electrodes).  Nested keys
               must contain pos, neg indicating, respectively, the
               positive polarity sensor and its reference (a string
               name) which may be another electrode (A1, lhz) or not
               (avg).

            """

            yhdr, doc_names, yhdr_md5 = self._load_yaml_docs(yhdr_f)

            # make sure the YAML dict doesn't step on basic top-level header info
            new_keys = yhdr.keys()
            for (h_key, h_type) in self._mkh5_header_types.items():
                if h_key in new_keys:
                    raise self.YAMLClobberError(self, h_key, yhdr_f)

            # enforce special case requirements here
            if "apparatus" in doc_names:
                for m in ["space", "fiducials", "sensors", "streams"]:
                    if m not in yhdr["apparatus"].keys():
                        msg = "{0} apparatus document {1} map not found".format(
                            yhdr_f, m
                        )
                        raise mkh5.YamlHeaderFormatError(msg)

            # self-identify
            yhdr["yhdr_file"] = yhdr_f
            yhdr["yhdr_file_md5"] = yhdr_md5
            return yhdr

        def _check_header(self):
            """enforce mandatory minimum mkh5 header data structure"""

            # check for mandatory keys and values of the right type
            header_keys = self._header.keys()
            for h_key, dtype in self._mkh5_header_types.items():
                if h_key not in header_keys:
                    msg = (
                        f'uh oh ... mandatory key "{h_key}" is missing from  '
                        "mkh5 dblock header:\n"
                    )
                    msg += pprint.pformat(self._header.keys())
                    raise RuntimeError(msg)

                if not isinstance(self._header[h_key], dtype):
                    msg = "uh oh ... bad header value datatype: "
                    msg += "{0} should be {1} not {2}".format(
                        h_key, dtype, self._header[h_key].__class__
                    )
                    raise RuntimeError(msg)

            # check the stream items
            mand_stream_keys = self._mkh5_header_stream_types.keys()
            mand_stream_types = self._mkh5_header_stream_types.values()
            for (k, v) in self._header["streams"].items():
                for sk, sv in v.items():
                    if sk in mand_stream_keys and not isinstance(
                        sv, self._mkh5_header_stream_types[sk]
                    ):
                        msg = 'uh oh ... stream {0}["{1}"] bad value datatype: '.format(
                            sk, sv
                        )
                        msg += "should be {1} not {2}".format(
                            self._mkh5_header_stream_types[sk], sv.__class__
                        )
                        raise RuntimeError(msg)

        def _check_streams(self, dblock):
            """enforce agreement between self._header streams and the data block

            Parameters
            ----------

            dblock (h5py.Dataset) readble mkh5 data block (reference)

            * checks the fields in _mkh5_header_stream_types
            _mkh5_header_stream_types = {
            'name': str,   # dig channel name, e.g., 'lle', 'MiPf'
            'jdx': int,    # column index in dblock_N dataset, 0, 1, ...
            'source': str, # source pfx[NNNN] where pfx = eeg|log|other, NNNN enumerates
            'dt': str,     # string np.dtype, e.g., '<f2', '<i4'
            # from mkh5._h5_update_eeg() where h5_path + dblock_id is the 

            
            Raises:
            
            RuntimeError on mismatch
            columns: labels, column order=jdx, and data type

            """
            self._check_header()  # first things first
            for jdx, col in enumerate(dblock.dtype.names):
                try:
                    assert col in self.header["streams"].keys()
                    assert jdx == self.header["streams"][col]["jdx"]
                    assert dblock.dtype[col] == self.header["streams"][col]["dt"]
                except:
                    msg = "uh oh ... header['streams'] is missing a data block column"
                    raise TypeError(msg)

            for k, v in self.header["streams"].items():
                try:
                    assert k in dblock.dtype.names
                    this_jdx = v["jdx"]
                    assert dblock.dtype.names[this_jdx] == k
                    assert dblock.dtype[this_jdx] == v["dt"]
                except:
                    msg = "uh oh ... header['streams'] has an extra stream"
                    raise TypeError(msg)

    # log data types ... ticks are uint64, everything else can be int16
    # _log_dtype = np.dtype([
    #     ("log_evticks", _evtick),
    #     ("log_evcodes", _evcode),
    #     ("log_ccodes", _log_ccode),
    #     ("log_flags", _log_flag),
    # ])

    # structure to merge dig marktrack and log info
    # FIX ME FOR EPOCHS
    _event_dtype = np.dtype(
        [
            ("evticks", _evtick),
            ("raw_evcodes", _evcode),
            ("log_evcodes", _evcode),
            ("log_ccodes", _log_ccode),
            ("log_flags", _log_flag),
        ]
    )

    _dblock_slicer_dtype = np.dtype(
        [
            ("start_samps", _epoch_t),
            ("anchor_samps", _epoch_t),
            ("stop_samps", _epoch_t),
        ]
    )

    # define a datatype for the bin-event table ... essentially a decorated log
    _bin_event_dtype = np.dtype(
        [
            ("evticks", _evtick),
            ("raw_evcodes", "i2"),
            ("log_evcodes", "i2"),
            ("log_ccodes", "u2"),
            ("log_flags", "u2"),
            ("bin_nums", "u2"),
            ("bin_descs", "S64"),  # icky ... hardcoded string lengths
        ]
    )

    # FIX ME ... non-event type epoch?
    _epoch_dtype = np.dtype(
        [
            ("anchor_ticks", _evtick),
            ("raw_evcodes", _evcode),
            ("epoch_starts", _evtick),
            ("epoch_stops", _evtick),
        ]
    )

    # for dumping instance info ...
    # pp = pprint.PrettyPrinter(indent=4)

    def __init__(self, h5name):

        """initialize and set mkh5 file name for this instance. If the file
           doesn't exist, create it. If it exists, test read/writeability

        Parameters:

            h5name (string) file path to the mkh5 format hdf5 file.

        """

        if isinstance(h5name, Path):
            h5name = str(h5name)

        # each mkh5 instance is tied to one and only one hdf5 format file
        logging.info(indent(2, "h5name is " + h5name))
        self.h5_fname = h5name

        # if file doesn't exist open, an empty hdf5 file
        if not os.path.isfile(self.h5_fname):
            self.reset_all()
        else:
            # file exists, warn if not readable or read-writable
            with h5py.File(self.h5_fname, "r") as h5:
                source_ver = __version__.split(r".")[0]  # major version

                if "version" in h5.attrs.keys():
                    file_ver = h5.attrs["version"].split(r".")[0]
                else:
                    file_ver = None

                if file_ver is not None and source_ver != file_ver:
                    msg = "version mismatch: source=={0} file {1}=={2}".format(
                        source_ver, self.h5_fname, file_ver
                    )
                    warnings.warn(msg)

            # try to open for read-write and let h5py deal with problems
            try:
                with h5py.File(self.h5_fname, "r+") as h5:
                    pass
            except:
                msg = "{0} is read only".format(self.h5_fname)
                warnings.warn(msg)

    # h5 introspection
    def _headers_equal(self, header1, header2):
        """returns boolean if all header dict keys and values are =="""

        raise NotImplemented("FIX ME WITH dpath.utils NOW")
        k1 = sorted(header1.keys())
        k2 = sorted(header2.keys())

        # if k1==k2 can iterate on either set of keys
        if k1 != k2 or any([header1[k] != header2[k] for k in k1]):
            return False
        else:
            return True

    # ------------------------------------------------------------
    # Public artifact tagging
    # ------------------------------------------------------------
    def garv_data_group(self, h5_data_group_path, skip_ccodes=[0]):
        """Run `pygarv` on all the dblocks under the `h5_data_group_path`.
        
        Parameters
        ----------
        h5_data_group_path : str
           name of the h5 datagroup containing the dblocks to screen

        skip_ccodes : list of uint, None ([0])
           dblocks with log_ccodes in the list are not scanned. Default
           is [0] to skip calibration blocks. Setting to None disables
           the skipper and scans all dblocks in the data group

        """
        dblock_paths = h5tools.get_dblock_paths(self.h5_fname, h5_data_group_path)

        for dbp in dblock_paths:
            hdr, dblock = self.get_dblock(dbp)

            # ccodes can only change on dig start or pause so
            # homogenous on unless there is some goofy log
            # poking going on ...
            log_event_idxs = np.where(dblock["log_evcodes"] != 0)[0]
            assert (
                dblock["log_ccodes"][log_event_idxs].max()
                == dblock["log_ccodes"][log_event_idxs].min()
            )
            log_ccode = dblock["log_ccodes"][log_event_idxs[0]]

            if skip_ccodes is not None:
                if log_ccode in skip_ccodes:
                    msg = "pygarv skipping {0} with " "log_ccode {1}".format(
                        dbp, log_ccode
                    )
                    print(msg)
                    continue
            print("pygarving {0} log_ccode {1}".format(dbp, log_ccode))
            with h5py.File(self.h5_fname, "r+") as h5:
                h5[dbp]["pygarv"] = pygarv._garv_dblock(hdr, dblock)

    # ------------------------------------------------------------
    # Public event code tag mapping and epoching utilities
    # ------------------------------------------------------------
    def get_event_table(self, code_map_f, header_map_f=None):
        """Reads the code tag and header extractor and returns an event lookup table

        Parameters
        ----------
        code_map_f : str
            Excel, YAML, or tab-separated text, see mkh5 docs for
            format details.

        header_map_f : str
            YAML header extractor file, keys match header keys, values specify
            name of the event table column to put the header data

        Returns
        -------
        event_table : pandas.DataFrame
           See Note.


        Note
        ----

        1. This sweeps the code tag map across the data to generate a lookup
           table for specific event (sequence patterns) where the rows specify:

           * slashpath to the mkh5 dblock data set and sample index
             for pattern-matching events.

           * all the additional information for that pattern given in
             the code tag map

           The event table generated from mkh5 data and the code_map
           specification is in lieu of .blf (for EEG epoching and
           time-locking), .rts (for event-to-event timing), and .hdr
           (for experimental design specification).


        2. ``ccode`` Special column. If the code tag map has a column
           named ``ccode`` the code finder finds events that match the
           code sequence given by the regex pattern **AND** the
           log_ccode == ccode. This emulates Kutas Lab `cdbl` event
           lookup and to support, e.g., the condition code == 0 for
           cals convention and blocked designs where the `ccode`
           varies block to block. If the code map does not specify
           a ``ccode``, column the `log_ccode` column is ignored for
           pattern matching.

        """

        # instantiate the codemapper w/ its map and code finder
        ctagger = CodeTagger(code_map_f)

        if "ccode" in ctagger.code_map.columns:
            msg = (
                f"\nAs of mkpy 0.2.0 to match events with a codemap regexp pattern, the\n"
                f"ccode column in {Path(code_map_f).name} must also match the log_ccode\n"
                f"in the datablock. If this behavior is not desired, delete or rename\n"
                f"the ccode column in the codemap."
            )
            warnings.warn(msg)

        # set up to extract info from the header
        hio = self.HeaderIO()
        if header_map_f is not None:
            hio.set_slicer(header_map_f)

        # fetch all data that have at least one mkh5 datablock (dblock_0)
        match_list = []
        dgroup_paths = h5tools.get_data_group_paths(self.h5_fname)
        with h5py.File(self.h5_fname, "r") as h5:
            for dgp in dgroup_paths:
                dblock_paths = h5tools.get_dblock_paths(self.h5_fname, dgp)
                for dbp in dblock_paths:
                    assert dgp in dbp  # group and data block must agree
                    hio.get(h5[dbp])  # need this for srate at least

                    # slice the header if there is an extractor
                    if hio._slicer is not None:
                        hdr_data = hio.get_slices()
                    else:
                        hdr_data = []

                    print("searching codes in: " + dbp)
                    event_idxs = (
                        h5[dbp]["log_evcodes"] != 0
                    )  # samples w/ non-zero events
                    dblock_ticks = h5[dbp]["dblock_ticks"][event_idxs]
                    crw_ticks = h5[dbp]["crw_ticks"][event_idxs]
                    raw_evcodes = h5[dbp]["raw_evcodes"][event_idxs]
                    log_evcodes = h5[dbp]["log_evcodes"][event_idxs]
                    log_ccodes = h5[dbp]["log_ccodes"][event_idxs]
                    log_flags = h5[dbp]["log_flags"][event_idxs]
                    # iterate on keys which are the code patterns
                    for idx, cm in ctagger.code_map.iterrows():
                        # matches is a list of lists of dict, one dict for each group
                        code_pattern_matches = ctagger._find_evcodes(
                            cm["regexp"], dblock_ticks, log_evcodes
                        )

                        if code_pattern_matches is not None:
                            for m in code_pattern_matches:
                                for mm in m:
                                    match_tick, anchor_tick, is_anchor = (
                                        None,
                                        None,
                                        None,
                                    )
                                    for k, v in mm:
                                        if k == "match_tick":
                                            match_tick = v
                                        if k == "anchor_tick":
                                            anchor_tick = v
                                        if k == "is_anchor":
                                            is_anchor = v
                                    assert all(
                                        [
                                            v is not None
                                            for v in [
                                                match_tick,
                                                anchor_tick,
                                                is_anchor,
                                            ]
                                        ]
                                    )

                                    if is_anchor:
                                        assert anchor_tick == match_tick
                                    else:
                                        assert anchor_tick != match_tick

                                    # ok, this is the tick of the pattern match
                                    # and it must be unique
                                    tick_idx = np.where(dblock_ticks == match_tick)[0]
                                    assert len(tick_idx) == 1

                                    sample_data = [
                                        # ("Index", idx),
                                        ("data_group", dgp),
                                        ("dblock_path", dbp),
                                        ("dblock_tick_idx", tick_idx[0]),
                                        ("dblock_ticks", dblock_ticks[tick_idx][0],),
                                        ("crw_ticks", crw_ticks[tick_idx][0]),
                                        ("raw_evcodes", raw_evcodes[tick_idx][0],),
                                        ("log_evcodes", log_evcodes[tick_idx][0],),
                                        ("log_ccodes", log_ccodes[tick_idx][0],),
                                        ("log_flags", log_flags[tick_idx][0]),
                                        (
                                            "epoch_match_tick_delta",
                                            0,
                                        ),  # an event is a one sample epoch
                                        ("epoch_ticks", 1),
                                        (
                                            "dblock_srate",
                                            hio.header["samplerate"],
                                        ),  # for conversion to times
                                    ]

                                    # extend sample data w/ the header information
                                    # which may be None
                                    sample_data = sample_data + hdr_data

                                    # extend sample_data w/ the match info and code map row
                                    sample_data = (
                                        sample_data + mm + list(zip(cm.index, cm))
                                    )
                                    match_list.append((sample_data))  # list of tuples
                                    # pprint.pprint(match_list)

        # handle no matches ...
        if len(match_list) > 0:

            event_table = pd.DataFrame([dict(m) for m in match_list])

            # codemap ccode triggers backwards compatibility
            # with Kutas Lab ERPSS cdbl
            if "ccode" in ctagger.code_map.columns:
                event_table = event_table.query("ccode == log_ccodes")

            # event_table.set_index("Index", inplace=True)

            self._h5_check_events(self.h5_fname, event_table)
            return event_table
        else:
            raise RuntimeError("uh oh ... no events found for {0}".format(code_map_f))

    def _h5_check_events(self, h5_f, e_table):
        """check the match event in event or epoch table agrees with the
           dblock data

        Parameters
        ----------
        h5_f : str
            path to mkh5 format hdf5 file
        e_table: (pandas.DataFrame, np.ndarray)
            as returned by mkh5.get_event_table()

        Returns
        -------
        None for success

        Raises
        ------
        RuntimeError on event_table[e] vs. dblock[e] mismatch or missing columns


        The minimum mandatory column names for an event table are

        * data_group: full slashpath to the h5py.Group covering a
          sequence of dblocks, e.g.,

              S001  
              Expt1/Session1/S047

        * dblock_path: full slashpath from the hdf5 root to one of the
          daughter dblock_N h5py.Datasets (without leading /), e.g.,

          S001/dblock_0
          Expt1/Session1/S047/dblock_12

        * dblock_ticks: the A/D sample counter which is also the row
          index of the dblock where the *matched* event appearing in
          the event table occurred. 

        * match_code: the event code of the regexp pattern-matched
          group for this event table row. There is one match code for
          each capture group in the regular expression pattern, so 
          the match code need not be the anchor code
        
        * All anchors are matches. Some matches may not be anchors

        * log_evcodes: the sequence of integer event codes occuring at
          each dblock tick in the original crw/log file

        """
        if isinstance(e_table, np.ndarray):
            e_table = pd.DataFrame(e_table)

        min_cols = subset = [
            "data_group",
            "dblock_path",
            "dblock_ticks",
            "log_evcodes",
            "match_code",
        ]
        for c in min_cols:
            if not c in e_table.columns:
                msg = 'mkh5 event table column "{0}"'.format(c)
                msg += "  is missing, all these are mandatory:" + " ".join(min_cols)
                raise RuntimeError(msg)

        with h5py.File(h5_f, "r") as h5:
            for index, e in e_table.iterrows():
                # These should only fail if the datablocks or event table have
                # been monkeyed with. Anyone who can do that can chase down
                # the assertion exception.

                data = h5[e["dblock_path"]][e["dblock_ticks"]]
                assert e["data_group"] in e["dblock_path"]

                # the log event code must be an anchor or a match
                if e["match_code"] != e["anchor_code"]:
                    assert e["match_code"] == data["log_evcodes"]
                else:
                    assert e["anchor_code"] == data["log_evcodes"]
                check_cols = [col for col in e.index if col in data.dtype.names]
                for col in check_cols:
                    assert data[col] == e[col]

    def _check_epochs_table(self, epochs_table):
        """check a set epochs table for event codes, epoch length, and offset

        Parameters
        ----------
        epochs_table : pd.DataFrame
           event table format with extra columns:
             epoch_ticks = fixed epoch duration in units of samples
             epoch_match_tick_delta = number of samples from epoch start to matched event code

        Returns
        ------- 
           None

        Raises
        ------
           ValueError
             if epoch event codes and data blocks column values do not match the datablocks or 
             epoch length and start offset values are not uniform across the epochs.

        """

        epoch_required_columns = ["epoch_ticks", "epoch_match_tick_delta"]

        # epochs tables are an extension of event tables, check the events first
        self._h5_check_events(self.h5_fname, epochs_table)

        # then epoch length and matched code offset (in samples)
        for c in epoch_required_columns:
            if c not in epochs_table.dtype.names:
                msg = "epochs table missing required column {0}".format(c)
                raise ValueError(msg)

            vals = np.unique(epochs_table[c])
            if len(vals) > 1:
                msg = "epochs table column {0} values must be the same: {1}".format(
                    c, vals
                )
                raise ValueError(msg)

    def _h5_check_epochs_table_name(self, h5_f, epochs_table_name):
        """look up and check a previously set epochs table

        Parameters
        ----------
        h5_f : str
           name of an mkh5 format HDF5 file, e.g., self.h5_fname or other
        epochs_table_name : str
           name of an epochs table, must exist in h5_f
        
        Returns
        -------
        None

        Raises
        ------
        ValueError
           if something is wrong with the lookup or table itself

        """

        eptbl = self.get_epochs_table(epochs_table_name, format="numpy")
        self._check_epochs_table(eptbl)

    def set_epochs(self, epochs_table_name, event_table, tmin_ms, tmax_ms):
        """construct and store a named EEG epochs lookup-table in self['epcochs']

        For storing in hdf5 the columns must be one of these:
          string-like (unicode, bytes)
          int-like (int, np.int, np.uint32, np.uint64)
          float-like (float, np.float32, np.float64)


        Parameters
        ----------
        epochs_table_name : string
            name of the epochs table to store

        event_table : pandas.DataFrame
            as returned by mkh5.get_event_table()

        tmin_ms : float
            epoch start in millseconds relative to the event, e.g, -500

        tmax_ms : float
            epoch end in millseconds relative to the event, e..g,
            1500, strictly greater than tmin_ms

        Returns
        -------
        None
            updates h5_f/EPOCH_TABLES_PATH/ with the named epoch table h5py.Dataset

        The epochs table is a lightweight lookup table specific to
        this mkh5 instance's hdf5 file,

          h5['epochs'][epochs_table_name] = epochs_table

        Event tables by default are "epochs" 1 sample long with 0
        prestimulus.

        This simply updates the prestimulus interval and length
        accordingly, adds the peri-event time interval information for
        slicing mkh5 datablocks and massages the event table
        (pandas.DataFrame) into a numpy ndarray for hdf5 storage.

        For reproducibility, by design epochs tables can be added to
        an mkh5 file but not overwritten or deleted. If you need to
        the revise the epochs, rebuild the mkh5 file from crws/logs
        with the ones you want.

        """
        with h5py.File(self.h5_fname, mode="r") as h5:
            if (
                mkh5.EPOCH_TABLES_PATH in h5.keys()
                and epochs_table_name in h5[mkh5.EPOCH_TABLES_PATH].keys()
            ):
                msg = (
                    f"epochs name {epochs_table_name} is in use, "
                    f"pick another name or use reset_all() to "
                    f"completely wipe the mkh5 file: {self.h5_fname}"
                )
                raise RuntimeError(msg)

        # event_table = self.get_event_table(code_map_f)
        if event_table is None:
            raise ValueError("uh oh, event_table is empty")
        self._h5_check_events(self.h5_fname, event_table)

        # ------------------------------------------------------------
        # 1. sanitize the pandas.Dataframe columns
        # ------------------------------------------------------------
        print("Sanitizing event table data types for mkh5 epochs table ...")

        # enforce Index data type is str or int
        # try:
        #     msg = None
        #     if event_table.index.values.dtype == np.dtype("O"):
        #         maxbytes = max(
        #             [len(x) for x in event_table.index.values.astype(bytes)]
        #         )
        #         index_dt_type = "S" + str(maxbytes)
        #     elif event_table.index.values.dtype == np.dtype(int):
        #         index_dt_type = "int"
        #     else:
        #         msg = "uh oh, cannot convert event table index column to bytes or integer"
        # except Exception as err:
        #     print(msg)
        #     raise err

        # # move Index into columns for santizing
        # event_table = event_table.reset_index("Index")

        # remap pandas 'O' dtype columns to hdf5 friendly np.arrays if possible
        tidy_table = pd.DataFrame()
        for c in event_table.columns:
            # do by column so failures are diagnostic. Pass in a copy
            # so nan handling can mod the series in place without
            # pd warning "setting value on copy"
            tidy_table[c] = self._pd_series_to_hdf5(event_table[c].copy())
        event_table = tidy_table

        # 2. define a numpy compound data type to hold the event_table
        # info and region refs

        # start with epoch_id
        epoch_dt_names = ["epoch_id"]
        epoch_dt_types = ["uint64"]

        # continue new dtype for event info columns, mapped to hdf5 compatible np.dtype
        event_table_types = [event_table[c].dtype for c in event_table.columns]
        for i, c in enumerate(event_table.columns):
            epoch_dt_names.append(c)
            epoch_dt_types.append(event_table[c].dtype.__str__())

        # events have sample ticks, epochs add timestamps
        epoch_dt_names += ["match_time", "anchor_time", "anchor_time_delta"]
        epoch_dt_types += ["int64"] * 3

        # construct the new dtype and initialize the epoch np.array
        epoch_dt = np.dtype(list(zip(epoch_dt_names, epoch_dt_types)))
        epochs = np.ndarray(shape=(len(event_table),), dtype=epoch_dt)

        # set the epoch_id counting index and copy the tidied event table
        epochs["epoch_id"] = [idx for idx in range(len(event_table))]
        for c in event_table.columns:
            epochs[c] = event_table[c]

        # 3. time lock each epoch to the match tick, and set the
        #    interval from the function arguments
        hio = self.HeaderIO()

        # init with nan and set to ms if epoch is in bounds
        is_in_bounds = np.zeros(len(epochs)).astype(bool)
        with h5py.File(self.h5_fname, "r+") as h5:
            # for i,e in event_table.iterrows():
            for i, e in enumerate(epochs):
                srate = e["dblock_srate"]

                # check event table sampling rate agrees w/ dblock
                dbp = e["dblock_path"]
                hio.get(h5[dbp])
                if srate != hio.header["samplerate"]:
                    msg = (
                        "{0}['samplerate']: {1} does not match "
                        "event table[{2}]['dblock_samplerate': "
                        "{3}"
                    ).format(dbp, hio.header["samplerate"], i, srate)
                    raise ValueError(msg)
                epoch_match_tick_delta = mkh5._ms2samp(tmin_ms, srate)
                start_samp = e["match_tick"] + epoch_match_tick_delta
                duration_samp = mkh5._ms2samp(
                    tmax_ms - tmin_ms, srate
                )  # must be non-negative
                if duration_samp <= 0:
                    msg = (
                        "epoch interval {0} {1} is less than one sample at "
                        "{3} ... increase the interval"
                    ).format(tmin_ms, tmax_ms, srate)
                    raise ValueError(msg)

                # move on after bounds check
                if start_samp < 0:
                    warnings.warn(
                        "data error: pre-stimulus interval is out of bounds left ... "
                        + "skipping epoch {0}".format(e)
                    )
                    continue
                elif start_samp + duration_samp > len(h5[dbp]):
                    warnings.warn(
                        "data error: post-stimulus interval is out of bounds right ... "
                        + "skipping epoch {0}".format(e)
                    )
                    continue
                else:
                    # if in bounds, overwrite np.nan with the epoch start and duration
                    is_in_bounds[i] = True

                    # set match and anchor tick, time, deltas
                    e["epoch_match_tick_delta"] = epoch_match_tick_delta
                    e["epoch_ticks"] = duration_samp

                    # add timestamps
                    e["match_time"] = int(0)
                    e["anchor_time_delta"] = int(
                        mkh5._samp2ms(e["match_tick"] - e["anchor_tick"], srate)
                    )
                    e["anchor_time"] = e[
                        "anchor_time_delta"
                    ]  # for consistency w/ epochs data columns

        # drop out of bounds epochs and check epochs are consistent
        epochs = epochs[is_in_bounds]

        # check the epochs for consistency
        self._check_epochs_table(epochs)

        # 4. add epoch table in the mkh5 file under /EPOCH_TABLES_PATH/epochs_table_name
        with h5py.File(self.h5_fname, "r+") as h5:
            epochs_path = f"{mkh5.EPOCH_TABLES_PATH}/{epochs_table_name}"
            ep = h5.create_dataset(epochs_path, data=epochs)
            attrs = {"tmin_ms": tmin_ms, "tmax_ms": tmax_ms}
            for k, v in attrs.items():
                ep.attrs[k] = v
        return None  # ok

    def export_event_table(self, event_table, event_table_f, format="feather"):
        """fetch the specified event table and save it in the specified format"""
        known_formats = ["feather", "txt"]  # txt is tab-separated
        if format not in known_formats:
            msg = "event_table export format must be 'feather' or 'txt'"
            raise ValueError(msg)

        # event_table = self.get_event_table(code_map_f)
        if event_table is None:
            msg = (
                "uh oh ... event_table is None for {0} ..." "nothing to export"
            ).format(code_map_f)
            raise ValueError(msg)

        if format == "feather":
            event_table.reset_index(inplace=True)
            event_table.to_feather(event_table_f)
        elif format == "txt":
            event_table.to_csv(event_table_f, sep="\t")
        else:
            raise RuntimeError()

    def get_epochs_table_names(self):
        """returns a list, possibly empty of previously named epochs tables

        """
        epochs_names = []
        try:
            with h5py.File(self.h5_fname, "r") as h5:
                epochs_names = [t for t in h5[mkh5.EPOCH_TABLES_PATH].keys()]
        except Exception:
            pass
        return epochs_names

    def _pd_series_to_hdf5(self, series):
        """normalize pandas.Series +/- missing or nans to array for hdf5 serialization

        Parameter
        ---------
        series : pandas.Series

        Returns
        -------
        arry_hdf5 : np.array, shape (1,), dtype=column scalar dtype

        Raises
        ------
        TypeError if series is not pandas.Series
        ValueError if series is empty
        EpochsTableDataError if series data doesn't convert to hdf5


        Supported data types
        
        * a single, homogenous scalar data type drawn from these
    
           float-like: float, np.float32, np.float64, etc.
           int-like: int, np.int32, np.int64, etc. 
           uint-like: np.uint32, np.uint64, etc.
           boolean-like: bool, np.bool
           string-like: str, bytes, unicode

        * missing data/NaNs are supported **except for boolean-like**

            NaN, None conversions as follows:
        
            Series type  |  from           | to hdf5
            ------------ | --------------  | ------------
            float-like   |  np.NaN, None   | np.nan
            int-like     |  pd.NaN, None   | np.nan, int coerced to float_
            uint-like    |  pd.NaN, None   | np.nan, int coerced to float_
            string-like  |  pd.NaN, None   | b'NaN'
            boolean-like |  pd.NaN, None   | not allowed
        
        
        Known dtypes according to pandas 0.21.0 return by infer_dtype
        
            empty (returned when all are None, undocumented in pandas)
         
            string, unicode, bytes, floating, integer,
            mixed-integer, mixed-integer-float, decimal,
            complex, categorical, boolean, datetime64,
            datetime, date, timedelta64, timedelta, time,
            period, mixed

        Approach: for mkh5 supported dtypes the pd.Series dtype 'O' has 2 cases:

            - not hasnans
               - values are str_like -> to bytes -> np.array
               - values are mixed types -> illegal, die
             
            - hasnans: two cases
               - the non-missing values are mixed types: illegal, die
               - the non-missing values are homogenous: handle by NaNs by type as above
                  - float_like -> missing/None are already np.nan -> np.array float
                  - int_like -> replace nans w/ max int of dtype  -> np.array float
                  - uint_like -> replace nans w/ max uint of dtype -> np.array float
                  - str_like -> replace nans w/ 'NaN' -> to bytes -> np.array bytes
                  - bool_like -> NaN/missing illegal, die

        """
        if not isinstance(series, pd.Series):
            msg = "wrong type {0}: must be pandas.Series".format(type(series))
            raise TypeError(msg)

        if not len(series) > 0:
            msg = "empty series"
            raise ValueError(msg)

        pd_num_like = ["floating", "integer", "decimal", "complex"]

        pd_bytes_like = [
            "string",
            "unicode",
            "bytes",
            # 'categorical', # ??
        ]

        pd_bool_like = ["boolean"]

        pd_type = pd.api.types.infer_dtype(
            series, skipna=False
        )  # mixed if missing values present
        # pd_data_type = pd.api.types.infer_dtype(series.dropna()) # mixed if mixed data
        pd_data_type = pd.api.types.infer_dtype(
            series, skipna=True
        )  # mixed if mixed data

        series_types = pd.unique([type(i) for i in series.values])
        data_types = pd.unique([type(i) for i in series.dropna().values])

        # homogonenous data w/ no missing values

        if series.dtype != "O":  #
            try:
                arry = np.array(series)
            except Exception as fail:
                print("column ", series.name)
                raise fail
            assert arry.dtype != "O"
            return arry
        else:
            # white-list the allowed conversions, all else fails

            # any combination of str-like values +/- missing data -> bytes +/- 'NaN
            if all([pd.api.types.is_string_dtype(dt) for dt in data_types]):
                if series.hasnans:
                    series.fillna(".NAN", inplace=True)
                # try each value to diagnosis if problem
                for v in series.values:
                    try:
                        np.array([v]).astype(np.string_)
                    except Exception as fail:
                        msg = ("\nvalue: {0}\n" "column: {1}").format(v, series.name)
                        print(msg)
                        raise fail

                # now try whole series
                try:
                    arry = np.array(series.values.astype(np.string_))
                except Exception as fail:
                    print("column ", series.name)
                    raise fail
                assert arry.dtype != "O"
                return arry

            # handle num-like +/- missing data
            elif pd_data_type in pd_num_like:
                try:
                    arry = np.array(series)
                except Exception as fail:
                    print("column ", series.name)
                    raise fail
                assert arry.dtype != "O"
                return arry
            else:
                # fail this blocks mixed numerics, boolean+NaN
                raise mkh5.EpochsTableDataError(pd_data_type, series)

    def get_epochs_table(self, epochs_name, format="pandas"):
        """look up a previously set epochs table by name

        Parameters
        ----------
        epochs_name : str
           name of a previously defined epochs table as set with an
           mkh5.set_epochs(event_table)
        format : str  {'pandas', 'numpy'}
           pandas.Dataframe or numpy.ndarray

        Returns
        -------
          epochs_table : pandas.Dataframe or numpy.ndarray

        Bytestrings from the hdf5 are converted to unicode epochs_table
        table returned

        """

        if format not in ["pandas", "numpy"]:
            msg = "format must be 'pandas' or 'numpy'"
            raise ValueError(msg)

        epochs_table = None
        with h5py.File(self.h5_fname, "r") as h5:
            epochs_path = f"{mkh5.EPOCH_TABLES_PATH}/{epochs_name}"
            epochs_table = h5[epochs_path][...]
        if epochs_table is None:
            msg = "epochs table not found: {0}".format(epochs_name)
            raise RuntimeError(msg)

        # clean up hdf5 bytestrings

        # FIX ME for NANs?
        dts = []
        for n in epochs_table.dtype.names:
            if epochs_table.dtype[n].kind == "S":
                dts.append((n, "U" + str(epochs_table.dtype[n].itemsize)))
            else:
                dts.append((n, epochs_table.dtype[n]))
        dts = np.dtype(dts)

        eptbl = np.empty(shape=epochs_table.shape, dtype=dts)
        for idx in range(epochs_table.shape[0]):
            for c in dts.names:
                value = copy.deepcopy(epochs_table[c][idx])
                if hasattr(value, "decode"):
                    eptbl[c][idx] = value.decode("utf8")
                else:
                    eptbl[c][idx] = value

        # run consistency check
        self._check_epochs_table(eptbl)

        if format == "pandas":
            eptbl = pd.DataFrame(eptbl)
            # eptbl.set_index("Index", inplace=True)
        return eptbl

    def _h5_get_epochs(self, epochs_name, columns=None):
        """merge datablock segments (event codes, EEG) with code tags and timestamps.

        Each row (1, n) in the epochs table is broadcast to an (m, n)
        array for the samples in the specified epochs interval and
        timestamps calculated for the anchor and match events.

        Epoch interval are extracted relative to the *matched* event
        in the code tag, see Yields for details.

        Parameters
        ----------
        epochs_name : string
            name of epochs table Dataset in h5['epochs']
        columns : list of strings, default = None extracts all
            column names to extract

        Yields
        ------
        epoch : numpy structured array shape = (m, n + 2) where

           * m == `epoch_table['epoch_ticks']`, the length of the epoch in samples

           * n == the number of columns in `epoch_table`

           * the starting sample of the epoch is calculated relative to the
             *matched* event via `epoch_table['epoch_match_tick_delta']`

           * `epoch[:, column]` == `epoch_table[column]` for `column`
             in `epoch_table.dtype.names`. This broadcasts the
             experimental event code tags to all samples in the epoch.

           epoch['match_time']: uint64
             epoch['match_time'] == 0  for the *matched* event

           epoch['anchor_time']: uint64
             epoch['anchor_time'] == 0 for the *anchor* event

        Note
        ----

        Iterating over this generator will fetch all the epochs given
        in epochs_name

        .. TO DO: implement hdf5 region refs

        """

        with h5py.File(self.h5_fname, "r") as h5:
            epochs_path = f"{mkh5.EPOCH_TABLES_PATH}/{epochs_name}"
            epoch_view = h5[epochs_path]
            epoch_cols = epoch_view.dtype.names

            # guard against irregular epochs
            assert len(np.unique(epoch_view["epoch_ticks"])) == 1
            assert len(np.unique(epoch_view["epoch_match_tick_delta"])) == 1
            for e in epoch_view:

                nsamp = e["epoch_ticks"]

                # fill nsamp rows x event info columns
                event_info = np.stack([e for n in range(nsamp)], axis=0)

                # set for epoch slice
                start, stop = None, None
                start_samp = e["match_tick"] + e["epoch_match_tick_delta"]
                stop_samp = start_samp + nsamp
                epoch_streams = h5[e["dblock_path"]][start_samp:stop_samp]

                # upconvert EEG columns float16 to float32 b.c. 2 byte floats
                # fight w/ feather (unsupported datatype), MATLAB
                # (cannot co-mingle w/ int64)
                f4_streams_dtype = []
                for name in epoch_streams.dtype.names:
                    if epoch_streams.dtype[name] == "float16":
                        f4_streams_dtype.append((name, "float32"))
                    else:
                        f4_streams_dtype.append((name, epoch_streams.dtype[name]))
                f4_streams_dtype = np.dtype(f4_streams_dtype)
                epoch_streams = np.array(epoch_streams, dtype=f4_streams_dtype)

                # merge epoch table, match_time, and datablock stream table column names
                all_cols = list(event_info.dtype.names)
                for c in epoch_streams.dtype.names:
                    if c not in all_cols:
                        all_cols.append(c)

                # use all available columns (default) or specified subset
                if columns is None:
                    epoch_dt_names = all_cols
                else:
                    for c in columns:
                        if not c in all_cols:
                            msg = "column {0} not found in epoch table or data block: ".format(
                                c
                            )
                            msg += " ".join(all_cols)
                            raise RuntimeError(msg)
                    epoch_dt_names = columns

                # ------------------------------------------------------------
                # ATTENTION: THIS SECTION IS HIGHLY PROCEDURAL AND BRITTLE
                # ------------------------------------------------------------
                # build data types
                epoch_dt_types = []
                for n in epoch_dt_names:
                    if n in epoch_streams.dtype.names:
                        epoch_dt_types.append(epoch_streams.dtype[n])
                    elif n in e.dtype.names:
                        epoch_dt_types.append(event_info.dtype[n])
                    else:
                        raise ValueError(
                            f"column {n} not found in dblock or epoch table"
                        )

                # # define dtype and initialize
                epoch_dt = np.dtype(list(zip(epoch_dt_names, epoch_dt_types)))
                epoch = np.ndarray(shape=(nsamp,), dtype=np.dtype(epoch_dt))

                # take the stream names first to protect the time
                # varying columns, then propagate the new info from
                # the epoch event.
                srate = e["dblock_srate"]
                assert e["match_time"] == 0
                for n in epoch_dt_names:
                    # these are already time-varying
                    if n in epoch_streams.dtype.names:
                        epoch[n] = epoch_streams[n]

                    # generate match, anchor time stamps and deltas
                    elif n == "match_time":
                        epoch[n] = [
                            int(mkh5._samp2ms(x - e["match_tick"], srate))
                            for x in range(start_samp, stop_samp)
                        ]
                    elif n == "anchor_time":
                        epoch[n] = [
                            int(mkh5._samp2ms(x - e["anchor_tick"], srate))
                            for x in range(start_samp, stop_samp)
                        ]
                    elif n == "anchor_time_delta":
                        epoch[n] = [
                            int(mkh5._samp2ms(x - e["anchor_tick_delta"], srate))
                            for x in range(start_samp, stop_samp)
                        ]

                    # broadcast event info
                    elif n in event_info.dtype.names:
                        epoch[n] = event_info[n]
                    else:
                        raise ValueError(
                            "uh oh ... unknown column {0} in epoch data extraction".format(
                                n
                            )
                        )
                # ------------------------------------------------------------
                yield (epoch)

    def get_epochs(self, epochs_name, format="numpy", columns=None):
        """ fetch single trial epochs in tabluar form

        Parameters
        ----------
        epochs_name : str
            name of previously set epochs table
        format : str {'numpy', 'pandas'}
        columns : list of str or None {'None'}
            the subset of column names to extract

        Returns
        -------
        epochs : numpy.ndarray or pandas.DataFrame
           epochs.shape == (i x m, n + 2) where

           i = the number of epochs, indexed uniquely by epoch_table['epoch_id']
           m = epoch length in samples
           n = the number of columns in the `epochs_name` epochs table

          See `_h5_get_epochs()` for details.

        attrs : dict
           stub 

        """

        if format not in ["numpy", "pandas"]:
            msg = f"format='numpy' or format='pandas' not {format}"
            raise ValueError(msg)

        epochs = np.array(
            [e for e in self._h5_get_epochs(epochs_name, columns=columns)]
        ).flatten()

        if format == "numpy":
            pass
        elif format == "pandas":
            epochs = pd.DataFrame(epochs)

            # cleanup bytestrings
            for col in epochs.columns:
                try:
                    # encode as utf8 or shrug and move on
                    epochs.loc[:, col] = epochs.loc[:, col].str.decode("utf8")
                except Exception as fail:
                    pass

        else:
            raise Exception("uncaught exception")

        # fetch the attrs for this epoch dataset
        with h5py.File(self.h5_fname, "r") as h5:
            attrs = dict()
            for k, v in h5[mkh5.EPOCH_TABLES_PATH][epochs_name].attrs.items():
                attrs[k] = v

        return epochs, attrs

    def export_epochs(self, epochs_name, epochs_f, file_format="h5", columns=None):
        """write previously set epochs to data in the specified file format

        Recommended epoch export formats for cross-platform data interchange

        Parameters
        ----------
        epochs_name : string
             must name one of the datasets in this h5['epochs']
        epochs_f : string
             file path and name of the data file
        file_format : string, {'h5', 'pdh5', 'feather', 'txt'}


        .. warning ::

           File formats other than h5 overwrite any file with the same
           name without warning.


        Note
        ----

        * h5 format:

          * the epochs are saved in the HDF5 file root as a dataset
            named `epochs_name`. Fails if such a dataset already
            exists.

          * 2-D rows x columns epochs data are stored as a single 1-D
            column vector (rows) of an HDF5 compound data type
            (columns). This HDF5 dataset is easily read and unpacked
            with any HDF5 reader that supports HDF5 compound data
            types.

        * pdh5 format: 2-D rows x columns epochs data are written to
          disk with `pandas.to_hdf` writer (via pytables). These
          epochs data are easily read into a `pandas.DataFrame` with
          `pandas.read_hdf(epochs_f, key=epochs_name)` and are also
          readable, less easily, by other HDF5 readers.

        * feather, txt formats: 2-D rows x columns epochs data are
          written to disk with `pandas.to_feather` (via pyarrow) and
          as tab-separated text with `pandas.to_csv(..., sep='\t')`.

        """

        # in case of Path
        epochs_name = str(epochs_name)
        epochs_f = str(epochs_f)

        known_formats = ["h5", "pdh5", "feather", "txt"]
        if file_format not in known_formats:
            msg = f"unknown file_format='{file_format}': must be one of {' '.join(known_formats)}"
            raise ValueError(msg)

        if file_format == "h5":
            (epochs, attrs) = self.get_epochs(
                epochs_name, format="numpy", columns=columns
            )
            with h5py.File(epochs_f, "w") as h5:
                epochs_dataset = h5.create_dataset(epochs_name, data=epochs)
                for k, v in attrs.items():
                    epochs_dataset.attrs[k] = v
        else:
            # non-hdf5 formats
            (epochs, attrs) = self.get_epochs(
                epochs_name, format="pandas", columns=columns
            )

            # dump with pandas
            if file_format == "pdh5":
                epochs.to_hdf(epochs_f, key=epochs_name, format="fixed", mode="w")
            elif file_format == "feather":
                epochs.to_feather(epochs_f)
            elif file_format == "txt":
                # don't write row count index
                epochs.to_csv(epochs_f, sep="\t", index=False)
            else:
                msg("unknown file epoch export file format: {0}".format(file_format))
                raise TypeError(msg)

        return None

    # ------------------------------------------------------------
    # PRIVATE (-ish) CRUD. These all wrap the hp5py.File()
    # in a context manager so user's don't have to.
    # ------------------------------------------------------------

    # data settin ops
    # def _h5_update_eeg_data(self, h5f, group_name, attr, data, yhdr, *args, **kwargs):
    def _h5_update_eeg_data(self, h5f, group_name, header, data, *args, **kwargs):

        """database-like CRUD to push .crw/.log data into the mkh5 format

        Parameters
        -----------
          h5f : str
             filepath to existing writable h5, else h5py Error
  
          group_name : str
              h5 file Group path name

          header : mkh5.HeaderIO.header
              built from .crw header + YAML info

          data : numpy record array 
              rows = samples 
              columns = ticks, events, log, individual channel data

          yhdr : dict
              contains supplemental information from yaml file (see
             `_load_yhdr`) args (stub) kwargs = passed to

          *args, **kwargs
             passed to h5py, e.g., compression, chunks

        Warning: When appending data to existing data headers are not
        checked for consistency`

        Use case 1: Create/New. This is the basic step to convert
        .crw/.log to the mkh5 data interchange format.

        Use case 2: Update/Append.  This behavior combines .crw/.log
        files to add cals, recover from restarts, combine sessions and
        such.

        Implementation:

        * mkio returns log info and the eeg strip chart incrementally
          indexed by A/D sample, ie., crw_ticks = 0 ... number of
          samples. This EEG data array is split on negative crw event
          code rows (pauses, data errors) into mkh5 datablocks of
          continuously sampled eeg.

        * The mkh5 datablock is the minimal unit, consisting of 

           * dblock_N (h5py.Dataset) a single numpy.ndarray log + eeg
                      stripchart

           * dblock_N.attr[json_header] (h5py.Attribute) the log + eeg
                      header information encoded as a JSON string. 

        * The processing to Create and Append .crw/.log as mkh5 datablocks is
          identical

          - count the number of existing datablocks in h5_path = N
          - create sequentially numbered datablocks at h5_path starting with N

        For Create/New, N == 0

        For Append N > 0

          group/dblock_n, group/dblock_n+1, ... group/dblock_n+m+m

        mkh5 datablock format: dblock_N

           Each continuous record is a new, sequentially
           numbered recording h5py.Group under input group_name.

           Under each such recording, each column in data is a new dataset.

           group_name/dblock_0/crw_ticks
           group_name/dblock_0/raw_evcodes
           ... 
           group_name/dblock_0/lle
           group_name/dblock_0/lhz
           ...
           group_name/dblock_0/MiPa
           ...
           group_name/dblock_0/the_last_channel

        """

        # ------------------------------------------------------------
        # 1. collect the boundaries of the continuous stretchs of .crw
        # data at
        #
        #   - beginning
        #   - negative event codes = pauses, data errors
        #   - end
        # ------------------------------------------------------------
        negative_raw_code_idxs = (data["raw_evcodes"] < 0).nonzero()[0]

        # white list pause mark codes for the dblock boundaries
        pause_idxs = [
            i
            for i in negative_raw_code_idxs
            if data["raw_evcodes"][i] in mkh5._dig_pause_marks
        ]

        # negative log codes are common, negative raw codes other than
        # pause marks are not
        if len(negative_raw_code_idxs) > len(pause_idxs):
            msg = "\n".join(
                [
                    "raw tick {0}: code {1}".format(i, data["raw_evcodes"][i])
                    for i in negative_raw_code_idxs
                    if data["raw_evcodes"][i] not in mkh5._dig_pause_marks
                ]
            )
            msg += (
                "\n{0} {1} unusual negative codes in raw marktrack ... "
                "make sure you know why."
            ).format(h5f, group_name)
            warnings.warn(msg)
        data_boundaries = [
            -1
        ]  # start with a boundary one sample before the first, i.e., at -1
        data_boundaries.extend(pause_idxs)  # add the boundaries

        # force a boundary at the last sample in case the file was closed without pausing
        datalen = len(data["raw_evcodes"])
        if data_boundaries[-1] != datalen - 1:
            data_boundaries = np.append(data_boundaries, datalen - 1)
            warnings.warn(
                "no pause mark at the last data sample ... make sure this is OK"
            )

        # (start, stop) tuples of data block row indices
        data_intervals = [
            (data_boundaries[i] + 1, data_boundaries[i + 1])
            for i in range(len(data_boundaries) - 1)
        ]

        # build the h5 datasets and set their header attr
        with h5py.File(h5f, "r+") as h5:
            # find and count datablocks already in the group
            dblock_ids = [k for k in h5[group_name].keys() if "dblock" in k]
            nextblock = len(dblock_ids)  # for the dblock_id counter
            for i, (start, stop) in enumerate(data_intervals):

                # split data into on the interval tuples
                dblock_id, dblock = None, None

                # ------------------------------------------------------------
                # write the dig data chunk as dblock_N
                # ------------------------------------------------------------
                dblock_id = "dblock_{0}".format(nextblock + i)
                dblock = h5[group_name].create_dataset(
                    dblock_id, data=data[...][start : stop + 1], **kwargs
                )
                # set this dblock ticks sequence
                dblock["dblock_ticks"] = range((stop + 1) - start)

                # set this dblock header
                header.set(dblock)

            # FIX ME: sanity check the data blocks samples total to data samples
        return None

    # ------------------------------------------------------------
    # *** PUBLIC *** CRUD
    # ------------------------------------------------------------
    def reset_all(self):
        """completely wipe out the mkh5 file and reset to empty without mercy"""
        with h5py.File(self.h5_fname, "w") as h5:
            # version new h5 files
            h5.attrs["version"] = __version__

    # create a new data set in specified group
    def create_mkdata(
        self, h5_path, eeg_f, log_f, yhdr_f, *args, with_log_events="aligned", **kwargs,
    ):
        """Convert Kutas lab ERPSS `.crw` and `.log` to the 
        `mkh5` hdf5 format.

        This merges dig `.crw`, `.log`, and user-specified `.yml` data into a tidy
        HDF5 dataset of continuous EEG recording + jsonic header.


        .. note::

           Log events are automatically truncated if log event codes
           occur after the end of the EEG data. This is rare but can
           happen when dig crashes or drops the last event code.


        Parameters
        ----------
        h5_path : str
             The full slashpath location in the `.h5` file where the
             new data blocks will be stored in the hdf5 file. Must be
             the full slashpath from the root without the leading
             slash.
        eeg_f : str
             file path to the `.crw` file.
        log_f : str or None
             file path to corresponding `.log` file, if any.
        yhdr_f : str
             file path to the YAML header file.
        with_log_events : {"aligned", "from_eeg", "none", "as_is"}, optional
             how to handle log file event codes (`log_evcodes`)
             relative to the eeg event codes (`raw_evcodes`) from the
             eeg recording.  
  
             `aligned` (default)
                   ensures eeg and log event code
                   timestamps are 1-1 but allows discrepant, e.g., logpoked,
                   event codes with a warning. Requires a log file. This
                   default is the mkpy.mkh5 <= 0.2.2 behavior.  

             `from_eeg` 
                   propagates the eeg event codes (dig mark track) to the `log_evcodes`
                   column. Requires `log_f` is `None`.

             `none`
                   sets `log_evcodes`, `log_ccode`, `log_flags` all to 0. Requires `log_f` is `None`.

             `as_is`
                   loads whatever codes are in the log file without
                   checking against the eeg data. Requires a log
                   file. Silently allows eeg and log event code
                   misalignment. Exceedingly dangerous but useful for
                   disaster recovery.

        *args : strings, optional
            passed in to `h5py.create_dataset()`
        *kwargs : key=values, optional
            passed in to `h5py.create_dataset()`, e.g., 
            `compression="gzip"`.


        Notes
        ----

        The EEG and event code data streams are snipped apart into
        uninterrupted "datablocks" at pause marks. Each data block has
        its own header containing information from the `.crw` file
        merged with the additional information from the YAML header
        file `yhdr_f`.

        Uncompressed ERPSS `.raw` files are also legal but there is no
        good reason to have them around. If the raw won't compress
        because it is defective it won't convert to `mkh5` either.
        There are no known useful `**kwargs`. HDF5 chunking fails when the
        size of datablock is smaller than the chunk and
        compression makes files a little smaller and a lot slower
        to read/write.


        Nathaniel Smith did all the hard work of low level ERPSS file
        IO.


        Examples

        .. todo::
           Give examples or link to snippets or examples

        """
        # clean up Path
        eeg_f = str(eeg_f)
        if log_f is not None:
            log_f = str(log_f)
        yhdr_f = str(yhdr_f)

        (attr, data) = self._read_raw_log(eeg_f, log_f, with_log_events=with_log_events)

        hio = mkh5.HeaderIO()
        hio.new(attr, yhdr_f)  # merge the .crw and yhdr into the new header

        # create the group and write the header
        with h5py.File(self.h5_fname, "r+") as h5:
            try:
                # create with data ... data.dtype is automatic
                group = h5.create_group(h5_path)
            except ValueError as fail:
                print("mkh5 path {0}".format(h5_path))
                raise fail

        # write out the data into hdf5 datablocks+attributes
        self._h5_update_eeg_data(self.h5_fname, h5_path, hio, data, *args, **kwargs)

        # FIX ME
        # self._check_data()

        return None

    # ------------------------------------------------------------
    # add eeg data to a group under the same header
    # ------------------------------------------------------------
    def append_mkdata(
        self, h5_path, eeg_f, log_f, yhdr_f, *args, with_log_events="aligned", **kwargs,
    ):
        """Append .crw, .log, .yhdr to an existing h5_path

        Extend an existing sequence of datablocks `h5_path/dblock_0`,
        ... `h5_path/dblock_N`, with the continuation,
        `h5_path/dblock_N+1`, ...

        The intended applicaton is to combine `.crw`, `.log` files
        together that could or should be grouped, e.g., to add
        separately recorded cals, recover from dig crashes, to pool an
        individuals data recorded in different sessions.


        Parameters
        ----------
        h5_path : str
             The full slashpath location in the `.h5` file where the
             new data blocks will be stored in the hdf5 file. Must be
             the full slashpath from the root without the leading
             slash.
        eeg_f : str
             file path to the `.crw` files.
        log_f : str or None
             file path to corresponding `.log` file.
        with_log_events : str
             how to handle the log event codes, see `mkh5.create_mkdata()` for details
        yhdr_f : string
             path to the YAML header file.


        Raises
        -------
        Warning
             If the new crw headers do not match the existing
             group attributes


        See Also
        ---------
        :meth:`~mkpy.mkh5.mkh5.create_mkdata`

        """
        # clean up Path
        eeg_f = str(eeg_f)
        if log_f is not None:
            log_f = str(log_f)
        yhdr_f = str(yhdr_f)

        # slurp crw/log
        (crw_hdr, crw_data) = self._read_raw_log(
            eeg_f, log_f, with_log_events=with_log_events
        )

        # build the new header
        new_hio = mkh5.HeaderIO()
        new_hio.new(crw_hdr, yhdr_f)
        self._h5_update_eeg_data(
            self.h5_fname, h5_path, new_hio, crw_data, *args, **kwargs
        )

    def delete_mkdata(self, sub_id):
        """delete a top-level group from the mkh5 h5 file without warning, see Notes about wasted space.

        Parameters

        sub_id (string) path to h5 group in the instance's h5file

        Notes:

        Use sparingly or not at all. hdf5 has no garbage collection,
        deleting groups leaves holes in the file unless the entire
        file tree is copied to a fresh file

        FIX ME: hdf5 notes hack around no garbage collection is to
        rewrite the gappy file to a new file ... this could be built
        in here.

        """
        with h5py.File(self.h5_fname, "r+") as h5:
            # with data ... data.dtype is automatic
            del h5[sub_id]

    # FIX ME, this can call _h5_get_dblock_slice
    def get_dblock(self, h5_path):
        """return a copy of header dict and numpy ndarray from the mkh5
        datablock at h5_path


        Parameters
        ----------
        h5_path : string
          full slashpath to a datablock in this mkh5 instance

        """

        with h5py.File(self.h5_fname, "r") as h5:
            hio = self.HeaderIO()
            hio.get(h5[h5_path])
            header = hio.header
            # dblock = copy.deepcopy(h5[h5_path].value) # deprecated
            dblock = copy.deepcopy(h5[h5_path][...])
        return (header, dblock)

    def _h5_get_dblock_slice(self, h5_f, h5_path, db_slice=None):
        """return a copy of header dict and numpy ndarray slice from the mkh5
        datablock from h5 file at h5_path.

        Parameters
        ----------
        h5_f : string
           path to mkh5 file
        h5_path : string
          full slashpath to a datablock in this mkh5 instance
        db_slice : slice (default = None)
          rows slice of the dblock to return, None returns entire dblock

        Returns
        -------
        (hdr, dblock_slice) : dict, np.ndarray
           entire dblock header dict for and the slice of dblock data
        """
        with h5py.File(h5_f, "r") as h5:

            # db_len = len(h5[h5_path].value)
            db_len = len(h5[h5_path][...])
            if db_slice is None:
                db_slice = slice(0, db_len)
            else:
                if db_slice.start < 0:
                    msg = "data block slice start < 0"
                    raise IndexError(msg)
                if db_slice.stop > db_len:
                    msg = "data block slice stop > data block length"
                    raise IndexError(msg)

            hio = self.HeaderIO()
            hio.get(h5[h5_path])
            header = hio.header
            dblock_slice = copy.deepcopy(h5[h5_path][db_slice])
        return (header, dblock_slice)

    # ------------------------------------------------------------
    # PUBLIC utilities
    # ------------------------------------------------------------
    def headinfo(self, pattern=".+"):
        """print header information matching the pattern regular expression to STDOUT

        Parameters
        ----------
        pattern: regexp 
           regular expression to look for in the slashpaths to
           datablocks and header information in this mkh5 format
           file. Default '.+' matches all header info.


        Assume we have previously constructed an mkh5 file `expts.h5`
        containing data for two experiments and multiple subjects in
        each and decorated with yaml header information about
        electrode locations.

        We may want to query and display more or less header
        information. Usually less since there is lots.

        Select the relevant information with regular expression
        pattern matching:
        
        .. code-block:: python

           > expts = mkh5.mkh5('expts.h5') # initialize the mkh5 object
           > expts.headinfo('Expt1/S001') # fetch all header info for Expt1/S001, all datablocks
           > expts.headinfo('Expt1/.*MiPa') # returns everything in any Expt1 header involving MiPa
           > expts.headinfo('Expt1/S001/apparatus/space/origin') # origin of sensor space Expt1/S003 
           > expts.headinfo('Expt1/S001/apparatus/sensors/MiPa/x') # x-coordinate of electrode MiPa

        """
        info = self._get_head(pattern)
        if info is not None:
            for k, v in info:
                print("{0}: {1}".format(k, v))
        else:
            warnings.warn("headinfo pattern {0} not found".format(pattern))

    def sethead(self, slash_vals, **kwargs):
        """update mkh5 dblock header information via ``dpath.utils`` style 
        slash path, value notation.


        The recommended method for adding information to mkh5 headers
        is via the YAML header file loaded when converting .crw/.log
        to mkh5
        
        myh5file.create_mkdata('my.crw', 'my.log', 'my.yhdr') 

        Use sethead() at your own risk. mucking with headers by hand
        is dangerous without a clear understanding of the mkh5 dataset
        and header attribute format and dpath.util behavior.

        Parameters
        ----------
        slash_vals : (str, value) 2-ple or list of them
           str is a slash path to an mkh5 dblock and on into the header
           value is JSON-ifiable scalar, dict, or sequence



        .. code-block:: python

          mydat = mkh5.mkh5('myfile.h5')
          mydat.sethead(('S01/dblock_0/long_subid', 'S0001_A')

          # probably a bad idea to set this only for first datablock
          mydat.sethead(('S01/dblock_0/npsych/mood_score', 4)
         
          # use a list to set for all dblocks
          spvs = [('S01/dblock_0/npsych/mood_score', 4),
                  ('S01/dblock_1/npsych/mood_score', 4),
                  ('S01/dblock_2/npsych/mood_score', 4),
                  ('S01/dblock_3/npsych/mood_score', 4),
                  ('S01/dblock_4/npsych/mood_score', 4),
                   ('S01/dblock_5/npsych/mood_score', 4), ]

        """

        # organize the input list of slash_vals by mkh5 datablock
        by_dblock = dict()
        for path, value in slash_vals:
            m = re.match(r"(.+/dblock_\d+)/(.+)", path)
            if m:
                assert len(m.groups()) == 2
                h5_dblock_path = m.groups()[0]
                h5_header_path = m.groups()[1]
                if h5_dblock_path not in by_dblock:
                    by_dblock[h5_dblock_path] = []  # first time thru
                by_dblock[h5_dblock_path].append((h5_header_path, value))

        # iterate by the dblocks found and update
        with h5py.File(self.h5_fname, "r+") as h5:
            for h5_dblock_path, hdr_slash_vals in by_dblock.items():
                self._h5_update_header(h5[h5_dblock_path], hdr_slash_vals, **kwargs)

    def gethead(self, pattern):
        """ get header values as a list of (slashpath, value) 2-ples suitable for passing to edhead"""
        return self._get_head(pattern)

    # ------------------------------------------------------------
    # introspection: headinfo and info
    # ------------------------------------------------------------
    def _get_head(self, pattern):
        """fetch all mkh5 dblock header info matching slashpath regexp pattern

        Parameters:

        pattern (regexp string) pattern to look for in the mkh5 headers

        Return
        ------
        matches : list
          list of 2-ples (slashpath, value)

        Example

        mydat._get_head('S0/dblock_0/streams/(crw_ticks|MiPa)')

        [
          (S01/dblock_0/streams/crw_ticks/jdx, 1),
          (S01/dblock_0/streams/crw_ticks/stream, 'new_crw_ticks'),
          (S01/dblock_0/streams/crw_ticks/name, 'crw_ticks'),
          (S01/dblock_0/streams/crw_ticks/dt, '<u4'),
          (S01/dblock_0/streams/MiPa/jdx, 22),
          (S01/dblock_0/streams/MiPa/stream, 'eeg0016'),
          (S01/dblock_0/streams/MiPa/name, 'MiPa'),
          (S01/dblock_0/streams/MiPa/dt, '<f2')
        ]

        """
        re.compile(pattern)

        h5_paths = h5tools.get_data_group_paths(self.h5_fname)
        db_slashpaths = []
        for path in h5_paths:
            db_slashpaths.append(h5tools.get_dblock_paths(self.h5_fname, path))

        matches = []
        with h5py.File(self.h5_fname, "r") as h5:
            for db_slashpath in db_slashpaths:
                for dbs in db_slashpath:
                    hio = self.HeaderIO()  # abundance of caution we are starting fresh
                    hio.get(h5[dbs])
                    hdr_paths = dpath.path.paths(hio.header, dirs=False, leaves=False)
                    for hdr_path in hdr_paths:
                        slash_path = "/".join([str(p[0]) for p in hdr_path])
                        full_path = dbs + "/" + slash_path
                        m = re.search(pattern, full_path)
                        if m:
                            matches.append(
                                (full_path, dpath.path.get(hio.header, hdr_path),)
                            )
                    del hio
        if len(matches) == 0:
            return None
        else:
            return matches

    def info(self):
        """return h5dump-ish overview of h5_path's groups/datasets/attributes and data
        Parameter:
      
        h5_path (string) h5 path to a group or dataset 

        Returns info (string) 
        """
        # headinfo = self.headinfo(**kwargs)
        headinfo = self._get_head(".+")
        h5_paths = np.unique(
            [re.match(r".*dblock_\d+", x).group() for x in [y[0] for y in headinfo]]
        )

        info = ""
        with h5py.File(self.h5_fname, "r") as h5:
            for n in h5_paths:
                info += "------------------------------------------------------------\n"
                info += "{0} {1}\n".format(n, h5[n].__doc__.strip())
                info += "------------------------------------------------------------\n"
                if isinstance(h5[n], h5py.Dataset):
                    info += "datablock attributes:\n"
                    hdr_slash_vals = self._get_head(n)
                    db_headinfo = "\n".join(
                        ["{0}: {1}".format(k, v) for k, v in hdr_slash_vals]
                    )
                    info += pprint.pformat(db_headinfo, indent=2, width=80)
                    info += "Data: {0}\n".format(h5[n][...].shape)
                    for col in h5[n].dtype.names:
                        info += "  {0} {1}".format(col, h5[n].dtype[col].name)
                        info += "  {0} .. {1}".format(h5[n][col][0:5], h5[n][col][-5:])
                        mqm = np.percentile(h5[n][col], [0, 25, 50, 75, 100])
                        info += " min-q-max: {0}\n".format(mqm)
                elif isinstance(h5[n], h5py.Group):
                    pass
                else:
                    raise ValueError("unknown h5py type: {0}".format(type(h5[n])))
                info += "\n"
        return info

    def calibrate_mkdata(
        self,
        id_name,
        cal_size=None,
        polarity=None,
        lo_cursor=None,
        hi_cursor=30,
        n_points=None,
        cal_ccode=None,
        use_cals=None,
        use_file=None,
    ):
        """fetch and apply normerp style calibration to raw/crw dataset. 

        This locates two cursors, one on either side of a an
        event-triggered calibration square wave step and measures
        average values in the interval +/- n_points around the cursors
        separately at each EEG data stream. The magnitude of the
        difference is the measure of the step. The calibration scaling
        factor for that stream is the average of the (trimmed)
        calibration pulses.

        Parameters
        ----------
        id_name : str
            h5 group name that is parent to mkpy format dblocks, id_name/dblocks
        cal_size : float
            magnitude of calibration square wave step in microvolts, e.g., 10
        polarity : (1,0) 
            ignored, and should be deprecated. In ERPSS this inverts
            all waveforms ... has nothing to do with calibration really.
        lo_cursor: float (positive value)
            magnitude of the low cursor offset from the calibration
            event in milliseconds
        hi_cursor: float (positive value)
            magnitude of the high cursor offset from the calibration
            event in milliseconds
        n_points : uint
            number of points on either side of each cursor to measure,
            interval = 2*n_points + 1
        cal_ccode : uint (default = 0)
            search for cal pulses only in dblocks where the ccode
            column == cal_ccode.  The standing kutas lab convention is
            cal ccode == 0
        use_cals : str (None defaults to `id_name`)
            slashpath to an alternate h5 group containing dblocks with the cal pulses
        use_file : str (None defaults to `self.f_name`)
            slashpath to an alternate mkpy format h5 data file.


        1. Calibration pulses are often recorded into the same `.crw`
           file or a separate file following data acquisition and then
           mkh5.append()-ed to a group. In both cases, the cal pulses
           appear in dblocks sister to the EEG data they are used to
           calibrate.

           Consequently the default calibration behavior is to search
           the dblocks daughter to self.h5_fname/id_name for the cal
           pulses.

           In rare cases, cal pulses are missing entirely and must be
           poached from another data group in the same hdf5 file or a
           data group in a different hdf5 file.

           Setting `use_cals` overrides the default group name.

           Setting `use_file` overrides the default self.f_name.

        2. The normerp way is to use the *ABSOLUTE VALUE* of the cal
           step regardless of polarity to adjust the amplitude of the
           +/- A/D recordings ... leaving the sign unchanged.
        
        3. The polarity flag -1 is used *ONLY* to switch the sign of
           the EEG and has nothing to do with the A/D scaling factor

        """

        # FIX ME: FINISH INPUT ERROR CHECK
        # FIX ME: this should throw future warning and be deprecated
        if polarity == 1:
            pass
        elif polarity == -1:
            warnings.warn(
                "polarity == -1 ... this is not necessary for negative cals and probably wrong."
                + "Use it only to invert the polarity of the EEG recording for some bizzare reason like"
                + "amps configured backwards with A1 (+) and Cz (-) instead of the usual Cz (+) and A1(-)"
            )
        elif polarity is not None:
            raise ValueError(
                "polarity flag must be 1 to leave EEG polarity unchanged or -1 to switch the sign"
            )

        # where to look for cals?
        if use_cals is None:
            use_cals = id_name  # default is daughter dblocks

        if use_file is None:
            use_file = self.h5_fname  # default is same mkpy file

        if None in [use_cals, use_file]:
            msg = "Calibrating {0} using cals from {1}/{2}"
            msg = msg.format(id_name, use_cals, use_file)
            warnings.warn(msg)

        # fetch a cal_info bundle from the use_cals group
        # ... cal_pulses are for inspection/plotting
        cal_info, cal_pulses = self._h5_get_calinfo(
            use_file,
            use_cals,
            cal_size=cal_size,
            lo_cursor=lo_cursor,
            hi_cursor=hi_cursor,
            n_points=n_points,
            cal_ccode=cal_ccode,
        )

        # FIX ME .. .implement min_cal_count ???
        with h5py.File(self.h5_fname, "r+") as h5:
            # datablock refs
            # n_dblocks = len([k for k in h5[id_name].keys() if 'dblock' in k])
            # dblocks = [h5[id_name + '/' + 'dblock_'+ str(i)] for i in range(n_dblocks)]

            dblock_paths = h5tools.get_dblock_paths(self.h5_fname, id_name)
            for dblock_path in dblock_paths:

                dblock = h5[dblock_path]
                hio = self.HeaderIO()
                hio.get(dblock)
                is_calibrated = any(
                    [
                        "cal" in key
                        for stream in hio.header["streams"]
                        for key in hio.header["streams"][stream].keys()
                    ]
                )
                if is_calibrated:
                    msg = (
                        "\n CAUTION skipping "
                        + dblock_path
                        + " ... appears to be already calibrated"
                    )
                    warnings.warn(msg)
                    continue

                print(
                    "Calibrating block {0} of {1}: {2}  ".format(
                        dblock.name, len(dblock_paths), dblock.shape
                    )
                )
                # get the names of colums with streams that string match 'dig_chan_' from attr metadata
                hio = self.HeaderIO()
                hio.get(dblock)
                attrs = hio.header
                strms = hio.header["streams"]

                # fail if chan names don't match
                if not cal_info.keys() == set(
                    [k for k, col in strms.items() if "dig_chan_" in col["source"]]
                ):
                    calchans = [c for c in cal_info.keys()]
                    print(
                        "Calibration datablock {0}: {1}".format(
                            use_cals, calchans.sort()
                        )
                    )
                    print(
                        "This data block {0}: {1}".format(
                            dblock.name, chan_names.sort()
                        )
                    )
                    raise ValueError(
                        "channel names in calibration data do not match data columns"
                    )

                # walk the cal info and apply it to this data ...
                # dt_uV = np.dtype(np.dtype([('uV',mkh5._mk_EEG)]))
                cal_slash_vals = []  # list of new attributes
                for chan, info in cal_info.items():
                    # print('  {0}'.format(chan), end='')
                    # dblock[chan] = dblock[chan]*(float(cal_size)/float(info['scale_by']))
                    # The normerp way ... scale by positive magnitude of cal step regardless
                    # of its sign.
                    scale_by = None
                    scale_by = float(info["scale_by"])
                    if scale_by < 0:
                        msg = (
                            "FYI found negative cal pulses {0} {1} ... "
                            "calibration will be OK".format(dblock_path, chan)
                        )
                        warnings.warn(msg)
                        scale_by = np.abs(scale_by)

                    # access by column *NAME*
                    dblock[chan] = dblock[chan] * (float(cal_size) / scale_by)

                    # This is pointless when the data are loaded into python
                    if polarity == -1:
                        dblock[chan] = -1.0 * dblock[chan]

                    # record this in the channel_metatdata
                    # chan_jdx = chan_jdxs[chan_names.index(chan)] # list version
                    # self._h5_set_dblock_attrs(dblock, streams=[(chan_jdx, 'calibrated', True),
                    #                                           (chan_jdx, 'cals', info)])
                    # chan_jdx = strms[chan]['jdx'] # dict version
                    cal_slash_vals += [("streams/" + chan + "/calibrated", True)]
                    cal_slash_vals += [("streams/" + chan + "/cals", info)]

                self._h5_update_header(dblock, cal_slash_vals)
                # self._h5_update_header(dblock, [('streams/' + chan + '/calibrated', True),
                #                              ('streams/' + chan + '/cals', info)]

    def _attr_to_slashpath(self, k, v, p, l):
        """ walk dictionary building a list of dpath friendly slashpaths, e.g., dblock.attr dicts"""
        p = p + "/" + k  # last key
        if not isinstance(v, dict):
            # l.append('{0}: {1}'.format(p, v))
            l.append((p, v))
            # print(leaf)
        else:
            for k1, v1 in v.items():
                self._attr_to_slashpath(k1, v1, p, l)
        return l

    @property
    def data_groups(self):
        return h5tools.get_data_group_paths(self.h5_fname)

    @property
    def dblock_paths(self):
        """an iterable list of HDF5 paths to all the data blocks in the mkh5 file"""
        dblock_paths = []
        h5_paths = self.data_groups
        for h5_path in h5_paths:
            dblock_paths += h5tools.get_dblock_paths(self.h5_fname, h5_path)
        return dblock_paths

    @property
    def data_blocks(self):
        """deprecated use mkh5.dblock_paths for a list of HDF5 paths to all the data blocks"""
        msg = (
            "mkh5.data_blocks is deprecated and will be removed in a future "
            "release, use mkh5.dblock_paths instead"
        )
        warnings.warn(msg, FutureWarning)
        return self.dblock_paths

    @property
    def epochs_names(self):
        return self.get_epochs_table_names()

    #
    def _load_eeg(self, eeg_f):
        """kutaslab .crw or .raw data loader, also populates self.dig_header

        Similar to MATLAB erpio2

        Parameters
        ----------
        eeg_f : str
           path to .crw or .raw data file

        Returns
        -------
        channel_names, raw_evcodes, record_counts, eeg, dig_header : tuple

        channel_names : list of str
           labels of EEG data channels in order from the .crw/.raw data header
        raw_evcodes : 1-D array of int
           event codes from mark track in each record
        record_counts : int
           number of 256-sample A/D data records as read from eeg_f
        eeg : np.ndarray (shape = (record_counts * 256, 1 + len(channel_names)
           array of A/D values knit together from the data records of
           256 samples each, for the event mark track and channels
        dig_header : dict
           key: values from the .crw/.raw header + some extra metadata


        * Pausing makes kutaslab "continuous" EEG data gappy. However,
          since the dig clock ticks stop during a pause,  ticks are
          not sample counts (at a fixed rate) not real-time clock ticks. 
        """

        # slurp low level NJS data
        with open(eeg_f, "rb") as fr:
            (
                channel_names,
                raw_evcodes,
                record_counts,
                eeg,
                dig_header,
            ) = mkio.read_raw(fr, dtype="int16")

        return channel_names, raw_evcodes, record_counts, eeg, dig_header

    def _check_mkh5(self):
        """error check structure and contents of self.eeg"""

        raise NotImplemented("FIX ME: code predates from mkh5 data format")

        # ------------------------------------------------------------
        # eeg
        # ------------------------------------------------------------
        if self.eeg is None:
            # fugedaboutit
            raise (ValueError("no eeg data"))

        # FIX ME check the data has the right shape

        # check for data errors in crw/raw
        max_chunk = max(self.dig_chunks["dig_chunks"])
        if not all(
            self.dig_chunks["dig_chunks"] == np.repeat(range(max_chunk + 1), 256)
        ):
            errmsg = (
                "{0} eeg dig records are not sequential, file may be corrupted: {1}"
            )
            errmsg = errmsg.format(self.dig_header["eegfile"], self.dig_chunks)
            warnings.warn(errmsg, DigRecordsNotSequential)

        # ------------------------------------------------------------
        # dig_header
        # ------------------------------------------------------------
        important_keys = [
            "subdesc",
            "samplerate",
            "expdesc",
            "nchans",
            "magic",
            "recordsize",
            "odelay",
            "recordduration",
            "dig_file_md5",
            "dig_file",
        ]

        # FIX ME: check the important keys have sensible values
        # fail on missing important keys and values
        for k in important_keys:
            if not k in self.dig_header.keys():
                raise (ValueError("dig_header key {0} not found".format(k)))

            if self._get_dig_header(k) is None or self._get_dig_header(k) == "":
                raise (ValueError("dig_header {0} value not found".format(k)))

        # ------------------------------------------------------------
        # location information if present, must be well behaved
        # ------------------------------------------------------------
        # if 'yhdr' in vars(self):
        #     # fail on duplicate electrode labels
        #     ll = [x.label for x in self.yhdr['sensors']]
        #     if not all(np.sort(ll) == np.sort(np.unique(ll))):
        #         raise(DuplicateLocationLabelError)

        # FIX ME: fail on missing location info any channel

    def _h5_update_header(self, h5_dblock, slash_vals, **kwargs):
        """
        add/overwrite dblock header info via dpath slashpath accessors

        Parameters
        ----------
        h5_dblock : (reference to h5py dataset in open, writeable mkh5 file)
          slash_vals a 2-pl (slash_path, value) or list of them, each settable by dpath.util.set
          kwargs ... keywords past to dpath.util.set

        Ex.  _h5_set_dblock_attr(h5dblock, (S01/dblock_0/samplerate, 250))
        Ex.  _h5_set_dblock_attr(h5dblock, [ (S01/dblock_0/streams/lle/calibrated, True), 
                                             (S01/dblock_0/streams/lhz/calibrated, True) ])
        """

        # promote singleton tuple to a list
        if not isinstance(slash_vals, list):
            slash_vals = [slash_vals]
        hio = mkh5.HeaderIO()
        hio.get(h5_dblock)
        hio._update_from_slashpaths(slash_vals)
        hio.set(h5_dblock)  # push header back into the dblock

    # ------------------------------------------------------------
    # dimension conversions samples <--> ms
    # ------------------------------------------------------------
    def _ms2samp(ms, srate):
        """convert (non-negative) ms intervals to samples"""
        period = 1000.0 / srate
        samp = np.int64(int(ms / period))
        return samp

    def _samp2ms(samp, srate):
        """convert n samples to ms at sample rate"""
        period = 1000.0 / srate  # in ms
        ms = np.float32(samp * period)
        return ms

    def _get_dblock_slices_at(
        anchors, n_before, n_duration, min_samp=None, max_samp=None
    ):
        """returns an array of slice tuples (start_sample, anchor, stop_sample)

        Parameters
        ----------
        anchors : nd.array, shape (n, )
            non-negative sample counters, e.g., 0, 27, 30004
        n_before: uint
            the number of samples before the anchor (positive integer)
        n_duration : uint
           epoch slice length in samples (positive integer) 

        Returns
        -------
        epochs : numpy.ndarray, dtype=mkh5._dblock_slicer_dtype       
            each dblock_slicer is a tuple of sample indices
            (start_idx, anchor_idx, stop_idx)
        

        This just does the sample math the sample math, minimal bounds checking
        

        """
        start_ticks = anchors - n_before  # *subtract* positive numbers
        stop_ticks = start_ticks + n_duration - 1
        epochs = np.array(
            [i for i in zip(start_ticks, anchors, stop_ticks)],
            dtype=mkh5._dblock_slicer_dtype,
        )
        # check bounds
        if min_samp is None:
            min_samp = np.iinfo(mkh5._epoch_t).min
        if any(epochs["start_samps"] < min_samp):
            msg = (
                "epoch starting sample is less than min_samp {0} "
                "... bad anchors or presampling?"
            ).format(min_samp)
            raise ValueError(msg)

        if max_samp is None:
            max_samp = np.iinfo(mkh5._epoch_t).max
        if any(epochs["stop_samps"] > max_samp):
            msg = (
                "epoch starting sample is greater than than {0} "
                "... bad anchors or duration?"
            ).format(min_samp)
            raise ValueError(msg)

        return epochs

    def _get_dblock_slicer_from_eventstream(self, event_stream, presamp, duration):
        """returns np.array of _dblock_slicer_dtype for non-zero events in event_stream
    
        Parameters
        ----------
        event_stream : 1-D array
            mostly 0's where non-zero values are taken to be event codes 
        presamp : uin64
            number of samples before the anchor event (positive number)
        duration : uint64
            number of samples in the slice 

        Returns
        -------
           slices : array of slices,   slice fails: array of slices


        Designed for use with dblock_N['log_evcodes'] data streams
        though will work with arbitrary 1-D array "event_streams".
        This allows programmatic construction of event stream.

        """
        # find non-zero event codes in the event_stream
        event_ticks = (event_stream > 0).nonzero()[0]

        slices = mkh5._get_dblock_slices_at(event_ticks, presamp, duration)
        inbounds = (0 <= slices["start_samps"]) & (
            slices["stop_samps"] < len(event_stream)
        )

        slice_fails = slices[inbounds == False]  # slice out bad
        slices = slices[inbounds == True]  # and drop them
        return (slices, slice_fails)

    # ------------------------------------------------------------
    # Model: data handling
    # ------------------------------------------------------------
    def _read_raw_log(self, eeg_f, log_f, with_log_events="aligned"):
        """NJS crw/log slurpers plus TPU decorations and log wrangling. 

        Parameters
        ----------
        eeg_f : str
           path to ERPSS .crw or .raw file

        log_f : str or None
           path to ERPSS .log file, if any. 

        with_log_events : str ("aligned", "from_eeg", "none", "as_is" )

           `aligned` (default) ensures eeg log event code timestamps
            are 1-1 but allows values, e.g, logpoked event codes with
            a warning. Requires log file. This is mkpy.mkh5 <= 0.2.2
            behavior.

           "from_eeg" propagates the eeg event codes (dig mark track)
           to the log_evcodes column. Not allowed with a log filename.

           `none` sets `log_evcodes`, `ccode`, `log_flags` all to 0.
           Not allowed with a log filename.

           `as_is` loads whatever codes are in the log file without
           checking against the eeg data. Requires a log file. Allows
           silent eeg and log event code misalignment. Excedingly
           dangerous but useful for disaster recovery.


        Returns
        -------
        log and raw data merged into a 2-D numpy structured array


        Notes
        -----

        `with_log_events` added in 0.2.3 to allow loading `.crw`
        files with badly mismatching and/or missing `.log` files. The
        change is backwards compatible, the default option
        `with_log_events='aligned'` is the same behavior as for
        `mkpy.mkh5` <= 0.2.2

        Handle logs with care. The crw is the recorded data log of
        eeg data and digital events (marktrack). The log file
        contains events only. Event discrepancies between the crw
        and log can also arise from data logging errors in the crw
        or log or both but these are rare. Discrepancies can also be
        introduced deliberately by logpoking the log to revise event
        codes. Also binary log files can be (mis)constructed from
        text files but there is no known instance of this in the
        past 20 years. Discrepancies involving the digital sample
        (tick) on which the event occurs are pathological, something
        in the A/D recording failed.  Discrepancies where sample
        ticks align but event code values differ typically indicate
        logpoking but there is no way to determine programmatically
        because the logpoked values can be anything for any reason.

        EEG data underruns. This can happen when dig fails and doesn't
        flush a data buffer. Rare but it happens.  The eeg + log data
        array columns have to be the same length, the choice is to pad
        the EEG data or drop the trailing log codes. Neither is good,
        the log events may have useful info ... stim and response
        codes. But these are available in other ways. For EEG data
        analysis, it is worse to pretend EEG data was recorded when it
        wasn't.

        Spurious event code 0 in the log. The crw marktrack 0 value is
        reserved for "no event" so a event code 0 in the log is a
        contradiction in terms. It is a fixable data error if the eeg
        marktrack at the corresponding tick is zero. If not, it is an
        eeg v. log code mismatch and left as such. There is one known
        case of the former and none of the latter.

        Each dig record contains 256 sweeps == samples == ticks. Within a
        record, each sweep is a clock tick by definition. The records in
        sequence comprise all the sweeps and provides.


        .. TO DO: some day patch mkio to yield rather than copy eeg

        """

        # modicum of guarding
        log_options = ["aligned", "as_is", "from_eeg", "none"]
        if not with_log_events in log_options:
            msg = f"with_log_events must be one of these: {' '.join(log_options)}"
            raise ValueError(msg)

        if log_f is None and with_log_events in ["aligned", "as_is"]:
            msg = f"with_log_events={with_log_events} requires a log file: log_f"
            raise ValueError(msg)

        if log_f is not None and with_log_events in ["from_eeg", "none"]:
            msg = f"to use with_log_events={with_log_events}, set log_f=None"
            raise ValueError(msg)

        # ------------------------------------------------------------
        # eeg data are read "as is"
        # ------------------------------------------------------------
        with open(eeg_f, "rb") as fr:
            (
                channel_names,
                raw_evcodes,
                record_counts,
                eeg,
                dig_header,
            ) = mkio.read_raw(fr, dtype="int16")
        assert len(raw_evcodes) == eeg.shape[0], "bug, please report"
        n_ticks = len(raw_evcodes)
        raw_event_ticks = np.where(raw_evcodes != 0)[0]
        raw_events = raw_evcodes[raw_event_ticks]
        n_raw_events = len(raw_events)

        # ------------------------------------------------------------
        # log data may get tidied
        # log_data[evcode, crw_tick, ccode, log_flag]
        # ------------------------------------------------------------
        log_data = None
        if log_f is not None:
            with open(log_f, "rb") as fid:
                log_data = np.array([row for row in mkio.read_log(fid)])

            # log event code ticks are not allowed to exceed EEG data ticks
            # under any circumstances. This can happen when dig crashes

            is_trailer = log_data[:, 1] > raw_event_ticks[-1]
            if any(is_trailer):
                oob_events = log_data[is_trailer]
                msg = (
                    f"{eeg_f} eeg data underrun {log_f}, "
                    f"dropping trailing log events {oob_events}"
                )
                warnings.warn(msg, LogRawEventCodeMismatch)
                log_data = log_data[~is_trailer]

        if with_log_events == "aligned":
            # aligned (default) is mkpy.mkh5 <= 0.2.2 legacy behavior
            assert log_data is not None, "bug, please report"

            # log zero codes are spurious iff the eeg marktrack at that tick is also 0
            is_spurious_zero = (log_data[:, 0] == 0) & (
                raw_evcodes[log_data[:, 1]] == 0
            )
            if any(is_spurious_zero):
                msg = f"dropping spurious 0 event code(s) in {log_f}: {log_data[is_spurious_zero]}"
                warnings.warn(msg)
                assert all(
                    log_data[is_spurious_zero][:, 0] == 0
                ), "this is a bug, please report"
                log_data = log_data[~is_spurious_zero]

            # fail if eeg and log event code ticks differ
            if not np.array_equal(log_data[:, 1], raw_event_ticks):
                align_msg = "eeg and log event code ticks do not align"
                raise RuntimeError(align_msg)

            # ticks are aligned if we get here, but warn of different values, e.g., logpoked
            mismatch_events = log_data[log_data[:, 0] != raw_events]
            if len(mismatch_events) > 0:
                mismatch_msg = (
                    "These log event codes differ from the EEG codes, "
                    "make sure you know why\n{mismatch_events}"
                )
                warnings.warn(mismatch_msg, LogRawEventCodeMismatch)

        elif with_log_events == "as_is":
            assert log_data is not None, "bug, please report"
            warnings.warn(
                f"not checking for event code mismatches in {eeg_f} and {log_f}"
            )

        elif with_log_events == "from_eeg":
            assert log_data is None, "bug, please report"
            warnings.warn(
                f"setting all log_evcodes to match EEG event codes codes in {eeg_f} "
            )
            log_data = np.array(
                [(raw_evcodes[tick], tick, 0, 0) for tick in raw_event_ticks]
            )

        elif with_log_events == "none":
            assert log_data is None, "bug, please report"
            warnings.warn(f"setting all log_evcodes, log_ccodes, log_flags to 0")
            log_data = np.zeros(
                (len(raw_events), 4), dtype="i4"
            )  # evcode, tick, ccode, log_flag
        else:
            raise ValueError(f"bad parameter value: with_log_events={with_log_events}")

        # ------------------------------------------------------------
        # construct output structured array
        # ------------------------------------------------------------
        #  tick and log info stream dtypes
        dt_names = [
            "dblock_ticks",
            "crw_ticks",
            "raw_evcodes",
            "log_evcodes",
            "log_ccodes",
            "log_flags",
            "pygarv",
        ]
        dt_formats = [
            mkh5._evtick,
            mkh5._evtick,
            mkh5._evcode,
            mkh5._evcode,
            mkh5._log_ccode,
            mkh5._log_flag,
            mkh5._pygarv,
        ]
        dt_titles = ["t_{0}".format(n) for n in dt_names]

        # eeg stream dtypes
        dt_names.extend([c.decode("utf8") for c in channel_names])
        dt_formats.extend(np.repeat(mkh5._mk_EEG, len(channel_names)))
        dt_titles.extend(
            ["dig_chan_{0:04d}".format(n[0]) for n in enumerate(channel_names)]
        )
        # mkh5 dblock dtype
        dt_data = np.dtype(
            {"names": dt_names, "formats": dt_formats, "titles": dt_titles}
        )

        # load eeg streams and build the crw_tick index
        data = np.zeros((len(raw_evcodes),), dtype=dt_data)
        data["crw_ticks"] = np.arange(n_ticks)
        # data['crw_ticks'] = np.arange(len(raw_evcodes))
        data["raw_evcodes"] = raw_evcodes

        # load the .log streams
        for (code, tick, condition, flag) in log_data:
            data["log_evcodes"][tick] = code
            data["log_ccodes"][tick] = condition
            data["log_flags"][tick] = flag

        # load eeg stream data
        for c, ch_name in enumerate(channel_names):
            data[ch_name.decode("utf8")] = np.array(eeg[:, c], dtype=mkh5._mk_EEG)

        # capture the new numpy metadata for variable columns
        # as a sequence to preserve column order
        # dblock_cols = [] # list version
        dblock_cols = dict()  # dict version
        for col_jdx, col_desc in enumerate(dt_data.descr):
            col_dict = None
            col_dict = {
                "jdx": col_jdx,
                "source": col_desc[0][0],
                "name": col_desc[0][1],
                "dt": col_desc[1],
                # "calibrated": False,  # still raw A/D
                # "cals": dict()        #
            }
            # dblock_cols.append(col_dict) # list version
            dblock_cols.update({col_desc[0][1]: col_dict})  # dict version

        # FIX ME ... check we don't clobber dig_head info

        attr = {"streams": dblock_cols}
        # patch np dtypes for jsonification ... ugh
        for k, v in dig_header.items():
            if isinstance(v, np.string_):
                attr[k] = str(v.decode("utf8"))
            elif isinstance(v, np.uint16) or isinstance(v, np.int16):
                attr[k] = int(v)
            else:
                attr[k] = v

        # decorate constant columns with more useful info
        attr["eeg_file"] = eeg_f
        attr["log_file"] = log_f if log_f is not None else "None"
        attr["uuid"] = str(uuid.uuid4())
        for k, fname in {"eeg_file_md5": eeg_f, "log_file_md5": log_f}.items():
            if fname is not None:
                with open(fname, "rb") as f:
                    attr[k] = hashlib.md5(f.read()).hexdigest()
            else:
                attr[k] = "None"

        # New version returns the header and stuff as a dict
        # jsonification occurs in dblock CRUD
        return (attr, data)

    def _h5_get_slices_from_datablock(dblock, slicer):
        """minimal mkh5 datablock epochs slicer

        Parameters
        ----------

        dblock : h5py.Dataset
            an open, readable mkh5 datablock, dblock_N
        slicer : numpy.ndarray, dtype=dtype _evticks
            i.e., tuples (start_samps, anchor_samps, stop_samps)

        Returns
        -------
            a copy of the data

        """
        epochs_data = []
        for e in slicer:
            # dblocks are sample rows down x data columns across
            # slicing here is a *row* slice, exactly what we want
            epochs_data.append(dblock[e["start_samps"] : e["stop_samps"]])

            # stack the arrays so access by name, e.g., MiPa returns a
            # subarray with sample rows down x epoch columns accross
        return np.stack(epochs_data, axis=1)

    def _h5_get_calinfo(
        self,
        h5f,
        group_name,
        n_points=None,
        cal_size=None,
        lo_cursor=None,
        hi_cursor=None,
        cal_ccode=None,
    ):
        """scan mkh5 datablocks under h5_path for cals and return channel-wise AD scaling info

        Parameters
        ----------

        h5f : str
           hdf5 file w/ conforming mkh5 data)group/dblock_N structure
        group_name : str
           mkh5 data_group to search for cal events and pulses
        n_points : uint
            number of samples average on either side of cursor
        cal_size : float, units of microvolts
            size of calibration pulse
        lo_cursor : float, units of milliseconds
            center of the pre-pulse window to average in computing the cal pulse amplitude
        hi_cursor : float, units of milliseconds
            center of the post-pulse window to average in computing the cal pulse amplitude
        cal_ccode : uint
            log condition code designated for calibration pulses, typically 0 by convention

        Returns
        -------

        dictionary including 'scale_by' factor and summary stats on the cals = (None,None) on fail

        Raises
        ------
        ValueError if missing kwargs 
        IOError if no kutaslab cals found in any of the group_name dblocks

        Return values coerced to float b.c. json can't serialze float16 .. cmon

        Unopinionated about what h5 group to search and works on any dblock with cals
        so it can be called on cals recorded with the EEG or in separate files. 

        Differences from normerp:

          - the pp_uV resolution argument is not used

          - there is no polarity parameter which has little to no point for data analysis

          - cal_cc (for condition code) is used instead of cal_bin
            since the single trial eeg and log files have no bins

        """
        # ------------------------------------------------------------
        # input check ...
        # ------------------------------------------------------------
        must_have = [n_points, cal_size, lo_cursor, hi_cursor, cal_ccode]
        if None in must_have:
            raise ValueError(
                "missing keyword arguments ... check for "
                + "n_points, cal_size, lo_cursor "
                + "hi_cursor, cal_ccode"
            )

        # ------------------------------------------------------------
        # scan the group_name datablocks for cals ...
        #  . cal epoch stacks are snippets of samples surrounding a pulse
        #  . there can be 1+ if cals are found in different datablocks
        # ------------------------------------------------------------
        with h5py.File(h5f, "r") as h5:

            # walk the group and gather up datablocks
            group = h5[group_name]
            dblock_sets = [
                g
                for g in group.keys()
                if "dblock" in g and isinstance(group[g], h5py.Dataset)
            ]
            if len(dblock_sets) == 0:
                raise Mkh5FormatError(
                    "datablocks not found in {0}".format(group_name)
                    + " check the id and/or load data"
                )

            # holds the calibration epoch stacks across datablocks, normally len == 1
            cal_stacks = []
            cal_dblock_ids = []  # for reporting only
            srate = nchans = None
            hio = self.HeaderIO()
            for gn in dblock_sets:
                g, attrs, consts, strms = None, None, None, None
                g = group[gn]
                # json -> dict
                # attrs = json.loads(g.attrs['json_attrs']) # deprecated
                # old_strms = attrs['streams'] # deprecated
                hio.get(g)  # fetch the dblock header for access
                strms = hio.header["streams"]
                # assert old_strms == strms

                # scan for calibration events using log_evcodes in case
                # bad cals have been manually logpoked
                # if any((g['log_ccodes'] == cal_ccode) & (g['log_evcodes'] < 0)):
                neg_cal_events = g["log_evcodes"][
                    np.where((g["log_ccodes"] == cal_ccode) & (g["log_evcodes"] < 0))
                ]
                if any(neg_cal_events):
                    msg = (
                        "negative event code(s) found for cal condition code "
                        + str(cal_ccode)
                        + " "
                    )
                    msg += " ".join([str(x) for x in neg_cal_events])
                    warnings.warn(msg)
                cal_event_ptrs = (
                    (g["log_evcodes"] > 0) & (g["log_ccodes"] == cal_ccode)
                ).nonzero()[0]

                # winner winner chicken dinner ... but horribly procedural
                if len(cal_event_ptrs) > 0:
                    # we have a cal block
                    print("Found cals in {0}".format(g.name))
                    cal_dblock_ids.append("{0}{1}".format(h5f, g.name))  # log it

                    # FIX ME: this is rude, we already knew this at dblock_0
                    # but this way it reports where the cals were found
                    # is_calibrated = any(['cals' in col.keys() for col in strms if 'dig_chan_' in col['source'] ])
                    # is_calibrated = any([v for k,v in strms.items() if k == 'calibrated'])
                    is_calibrated = any(
                        [
                            "cals" in col.keys()
                            for k, col in strms.items()
                            if "dig_chan_" in col["source"]
                        ]
                    )
                    if is_calibrated:
                        msg = (
                            group_name
                            + "/"
                            + gn
                            + " cannot access calibration pulses, they have already been scaled to uV"
                        )
                        raise RuntimeError(msg)

                    # check sample rate and channels against the previous block (if any)
                    if not (srate is None) and hio.header["samplerate"] != srate:
                        raise ValueError(
                            "srate in block {0}: {1}".format(
                                gn, hio.header["samplerate"]
                            )
                            + "does not match previous data block: {0}".format(srate)
                        )

                    if not (nchans is None) and hio.header["nchans"] != nchans:
                        raise ValueError(
                            "number of channels in block {0}: {1}".format(
                                gn, hio.header["nchans"]
                            )
                            + "does not match previous data block: {0}".format(nchans)
                        )

                    # set params this datablock ...
                    srate = hio.header["samplerate"]
                    nchans = hio.header["nchans"]

                    # humans use ms ...
                    lcs = mkh5._ms2samp(
                        lo_cursor, srate
                    )  # in negative samples b.c. of normerp incantations
                    hcs = mkh5._ms2samp(hi_cursor, srate)

                    # computers use samples ...
                    presamp = (
                        -1.0 * lcs
                    ) + n_points  # presampling is a magnitude (positive) for epoch calc
                    duration = hcs + n_points + presamp + 1

                    # returns an nd.array, access by data column name
                    # return subarray: duration samples x epochs
                    # (cal_slicer, fails) = self._get_dblock_slicer_from_eventstream(g['raw_evcodes'], presamp, duration)
                    (cal_slicer, fails,) = self._get_dblock_slicer_from_eventstream(
                        g["log_evcodes"], presamp, duration
                    )
                    if len(fails) > 0:
                        warnings.warn(
                            "dropping {0} cal epochs out of data bounds".format(
                                len(fails)
                            )
                        )

                    cal_stacks.append(mkh5._h5_get_slices_from_datablock(g, cal_slicer))

            # typically cals in one dblock tho no harm in more if they are good
            if len(cal_stacks) < 1:
                raise (
                    RuntimeError(
                        "cal events not found in file {0} ".format(h5f)
                        + "for {0} dblocks and log_ccode {1}".format(
                            group_name, cal_ccode
                        )
                    )
                )
            if len(cal_stacks) > 1:
                warnings.warn(
                    "found {0} datablocks with cal events and using all of them".format(
                        len(cal_stacks)
                    )
                    + "if this is unexpected check the crw/log and cal files"
                )

            # combine cal events from the dblocks into one stack,
            # samples down, events across, each element in sub array
            # is a row of dblock
            cal_set = np.hstack(cal_stacks)

            # pull the datablock column info down from the attrs/header

            # colmdat = json.loads(g.attrs['streams']) # deprecated
            # chan_names = [c['name'] for c in strms if 'dig_chan_' in c['source']] # list version
            chan_names = [
                c["name"] for k, c in strms.items() if "dig_chan_" in c["source"]
            ]  # dict version
            cal_factors = dict()

            for c, n in enumerate(chan_names):
                # ------------------------------------------------------------
                # auto trim the data FIX ME ... parameterize configurable someday
                # ------------------------------------------------------------
                q75, median, q25, iqr, = None, None, None, None
                delta_min, delta_max = None, None
                deltas, good = None, None

                # deltas are cal pulse step size (n, ) for n channels

                # float16 version
                # deltas = (cal_set[n][-(1+n_points*2):,:] - \
                #             cal_set[n][:(1+n_points*2),:]).mean(axis=0)

                # float64 version ... scaling 12-bit AD x 1e5 is safe for float64
                deltas = (
                    cal_set[n][-(1 + n_points * 2) :, :]
                    - cal_set[n][: (1 + n_points * 2), :]
                )
                deltas_e5 = 1e5 * np.array(deltas, dtype="<f8")
                deltas = 1e-5 * deltas_e5.mean(axis=0)

                # trim the deltas
                q75, median, q25 = np.percentile(deltas, [75, 50, 25])
                iqr = q75 - q25
                delta_min = median - (1.5 * iqr)
                delta_max = median + (1.5 * iqr)
                good = deltas[(delta_min < deltas) & (deltas < delta_max)]

                if len(good) == 0:
                    msg = (
                        "uh oh ... {0} channel {1}:{2} has no cal pulses "
                        "after trimming at median +/- 1.5IQR"
                    ).format(self.h5_fname, c, n)
                    raise ValueError(msg)

                if len(good) < 0.5 * len(deltas):
                    msg = (
                        "{0} channel {1}:{2} ... less than half the cal pulses remain "
                        "after trimming at median +/- 1.5IQR. "
                        "Do you know why?"
                    ).format(self.h5_fname, c, n)
                    warnings.warn(msg)
                # numpy may leave some as float16 if it can ... makes
                # json serializer unhappy
                cal_args = dict(
                    {
                        "n_points": int(n_points),
                        "cal_size": float(cal_size),
                        "lo_cursor": float(lo_cursor),
                        "hi_cursor": float(hi_cursor),
                        "cal_ccode": int(cal_ccode),
                    }
                )
                cal_factors.update(
                    {
                        n: {
                            "cal_srate": float(srate),
                            "cal_dblock": cal_dblock_ids,
                            "cal_args": cal_args,
                            "scale_by": float(good.mean()),
                            "var": float(good.var()),
                            "median": float(median),
                            "iqr": float(iqr),
                            "n_cals": int(len(good)),
                            "n_trimmed": len(deltas) - len(good),
                        }
                    }
                )
        return (cal_factors, cal_set)
        # ------------------------------------------------------------
        # end fetch calibration information
        # ------------------------------------------------------------

    # ------------------------------------------------------------
    # View
    # ------------------------------------------------------------
    def plotcals(self, *args, **kwargs):
        """visualize cal pulses and scaling factors used to convert to
        microvolts
        """

        calinfo = cal_stack = None
        print("Plotting cals")
        (calinfo, cal_stack) = self._h5_get_calinfo(*args, **kwargs)
        if calinfo is None or len(calinfo.keys()) == 0:
            raise Mkh5CalError(
                "no cals found in " + " ".join([str(arg) for arg in args])
            )

        # FIX ME ... legacy vars
        h5f = args[0]
        group_name = args[1]

        # ------------------------------------------------------------
        # Cal snippets at each channel
        # ------------------------------------------------------------
        ch_names = [x for x in calinfo.keys()]
        nchans = len(ch_names)

        n_col = 4
        f, ax = plt.subplots(
            np.ceil(nchans / float(n_col)).astype("int64"),
            n_col,
            figsize=(12, 8),
            facecolor="k",
        )
        calcolors = ["y", "m"]

        # 'hi_cursor': 50.0, 'cal_size': 10.0,
        # 'cal_ccode': 0, 'lo_cursor': -50.0, 'n_points': 3}

        # for c in range(nchans):
        for c, ch in enumerate(ch_names):
            cinf = calinfo[ch]
            cal_args = cinf["cal_args"]
            srate = cinf["cal_srate"]
            n_points = cal_args["n_points"]
            lo_cursor = n_points
            hi_cursor = len(cal_stack[ch]) - (n_points + 1)
            lo_span = range(lo_cursor - n_points, lo_cursor + n_points + 1)
            hi_span = range(hi_cursor - n_points, hi_cursor + n_points + 1)

            # relative to event @ sample 0
            cal_samps = range(
                lo_cursor - n_points, lo_cursor - n_points + len(cal_stack[ch])
            )
            a = ax[int(c / n_col), c % n_col]
            # a.set_axis_bgcolor('k')
            a.set_facecolor("k")
            a.set_ylabel(ch, color="lightgray", rotation=0, horizontalalignment="left")

            # box the points averaged
            a.axvspan(lo_span[0], lo_span[-1], color="c", alpha=0.5)  # ymax=0.5,
            a.axvspan(hi_span[0], hi_span[-1], color="c", alpha=0.5)  # ymax=0.5,
            # mark the cursors
            a.axvline(lo_cursor, color="r")
            a.axvline(hi_cursor, color="r")
            lpc = a.plot(cal_samps, cal_stack[ch], ".-", color=calcolors[c % 2])

        f.set_facecolor("black")
        st = (
            f"calibration pulses from: "
            f"{' '.join([str(arg) for arg in args])}\n"
            f"{' '.join([k + '=' + str(v) for k, v in kwargs.items()])}"
        )
        f.suptitle(st, color="lightgray")
        # plt.show()
        return (f, ax)


# TPU
class LocDat:
    """map Kutas lab spherical coordinates and Brainsight
    .elp data files to 3-D cartesian XYZ 


    Coordinates

       LocDat native positions are in Cartesian 3-space

       Origin is center of head

       Orientation is RAS: X+ = Right, Y+ = Anterior, Z+ = Superior
    
       Cartesian coordinates come in as triples: x, y, z

       Polar coordinates come in as triples: radius, theta, z

    Kutaslab

       Kutaslab topo coordinates are spherical come in as radius, theta, phi
       triples (see topofiles for theta, phi) and get mapped to x,y,z

       * origin is between the ears (co-planar with 10-20 temporal line)

       * vectors from the origin at angles (degrees)

          * theta = 0 points toward right ear, along interaural line,
            90 points to forehead along midline

          * phi = 0 points to the vertex, 90 points to the temporal line
    """

    def __init__(self, type, label, coord, pos, distance_units=None, angle_units=None):
        """initialize LocDat

        Parameters
        ----------
        type: str (electrode, fiducial, scalp, ...)

        label: str (lle, MiPa, Fz, Nasion, scalp37, ...)

        coord: str (cartesian | polar)

        pos: array of float, [x, y  z] | radius, theta, phi)
           See details

        distance_units: str (cm | inch)

        angle_units: str (deg | rad)
        """

        # check arguments ... sort of
        assert len(pos) == 3
        assert distance_units

        # capture positional arguments
        self.type = type
        self.label = label
        self.coord = coord
        self.distance_units = distance_units
        self.angle_units = angle_units

        # capture cartesian option
        if coord == "cartesian":
            self.x = self.y = self.z = None
            self.x = pos[0]
            self.y = pos[1]
            self.z = pos[2]

        if coord == "polar":
            # insist on sensible angle_units for polar coordinates
            assert angle_units == "degrees" or angle_units == "radians"

            self.radius = self.theta = self.phi = None
            self.radius = pos[0]
            self.phi = pos[1]
            self.theta = pos[2]

            if self.angle_units == "degrees":
                toradians = (2.0 * np.pi) / 360.0  # conversion factor
                self.theta_in_radians = self.theta * toradians
                self.phi_in_radians = self.phi * toradians
            else:
                self.theta_in_radians = self.theta
                self.phi_in_radians = self.phi

            # p projects onto x-y given phi,
            # so p == 1.0 at phi == 90 and < 1 otherwise
            p = self.radius * np.sin(self.phi_in_radians)
            self.x = p * np.cos(self.theta_in_radians)
            self.y = p * np.sin(self.theta_in_radians)
            self.z = self.radius * np.cos(self.phi_in_radians)
