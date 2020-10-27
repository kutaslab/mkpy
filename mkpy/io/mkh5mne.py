"""import mkpy5 HDF5 data files to MNE Raw and Epochs, savable as .fif files"""

from pathlib import Path
import warnings
import logging
from datetime import datetime, timezone
from copy import deepcopy
import re
import yaml
import json
import numpy as np
import pandas as pd
import mkpy.mkh5 as mkh5
from mkpy import dpath  # local fork
from mkpy import __version__ as mkpy_version

import mne
from mne.io.constants import FIFF
from mne.utils.numerics import object_hash  # for comparing MNE objects


# TODO simple logging
logger = logging.getLogger("mneio_mkh5")  # all for one, one for all
logger.propoagate = False  # in case of multiple imports

__version__ = mkpy_version

# ------------------------------------------------------------
# globals

# info = INFO
# quiet = WARN
# all = DEBUG
VERBOSE_LEVELS = ["info", "quiet", "debug"]

MNE_STREAM_TYPES = ["eeg", "eog", "stim", "misc"]
MNE_MIN_VER = (0, 20)  # major, minor

# ------------------------------------------------------------
# mkh5 specific

# requires header info introduced in mkh5 0.2.4
MKH5_MIN_VER = (0, 2, 4)  # major, minor, patch

KWARGS = {
    "dblock_paths": None,  # optional, selects listed dblock_paths
    "garv_interval": None,  # optional
    "fail_on_info": False,  # optional
    "fail_on_montage": True,  # optional
    "apparatus_yaml": None,  # optional
    "verbose": "info",  # optional
    "ignore_keys": [],  # optional
}

# these info keys can vary by mkh5 dblock, exclude from identity tests
IGNORE_INFO_KEYS = ["file_id", "meas_id", "proj_name", "subject_info"]


# EPOCHS_KWARGS = {
#     "epochs_name": None,  # mandatory
#     "epoch_id": "epoch_id",  # mkpy.mkh5 > 0.2.3 default
#     "time": "match_time",  # mkpy.mkh5 > 0.2.3 default
# }


# ------------------------------------------------------------
# base class for informative YAML header format errors
class Mkh5HeaderError(Exception):
    """used when mkh5 header is not compatible with building MNE data structures

    Parameters
    ----------
    message: str
      printed message

    dblock_path: str
      mkh5 dblock_path the header came from

    bad: dict, optional
       if present is dumped as a YAML str to show the (sub) dictionary
       that threw the exception.

    :meta private:
    """

    def __init__(self, message, dblock_path=None, bad=None):
        dbp_str = (
            "" if dblock_path is None else f"in data block: {dblock_path} header, "
        )
        bad_str = "" if bad is None else yaml.safe_dump(bad, default_flow_style=False)
        self.args = (dbp_str + self.args[0] + ", check the .yhdr YAML\n" + bad_str,)


class Mkh5HeaderKeyError(Mkh5HeaderError):
    """Missing a key required for MNE import"""


class Mkh5HeaderValueError(Mkh5HeaderError):
    """value is the wrong type for MNE import"""


class Mkh5HeaderTypeError(Mkh5HeaderError):
    """illegal value for MNE import"""


# ------------------------------------------------------------
# miscellaneous exceptions
class Mkh5FileAccessError(Exception):
    def __init__(self, msg):
        self.args = (msg,)


class Mkh5InfoUpdateError(Exception):
    """report failed info update attempts"""

    def __init__(self, mne_info_key, bad_value):
        msg = "failed to set mne info[{mne_info_key}] = {bad_value}"
        self.args = (msg,)


class Mkh5DblockPathError(Exception):
    """tried to access a non-existent datablock

    h5py also throws an error but the message is generic
    "object not found" without specifying what object.
    """

    def __init__(self, fail_msg, mkh5_f, dbp):
        msg = f"{fail_msg}: {mkh5_f} {dbp}"
        self.args = (msg,)


# ------------------------------------------------------------
# mkh5 epochs  table errors
class EpochsMkh5EpochsNameError(ValueError):
    """tried to access a non-existent epochs table"""

    def __init__(self, mkh5_f, epochs_name):
        msg = (
            f"in {mkh5_f} cannot locate epochs table {epochs_name}, "
            "check mkh5.get_epoch_table_names()"
        )
        self.args = (msg,)


class EpochsMkh5ExcludedDataBlockError(ValueError):
    """tried to access a non-existent epochs table"""

    def __init__(self, mkh5_f, epochs_name, missing_dblocks):
        msg = (
            (
                f"epochs table {epochs_name} requires data the following "
                f"{mkh5_f} dblock_paths, include them them to list of selected"
                f"dblock_paths=[...] or set dblock_paths=None to select all: "
            )
            + "["
            + ", ".join([dbp for dbp in missing_dblocks])
            + "]"
        )
        self.args = (msg,)


class EpochsMkh5ColumnNameError(ValueError):
    """non-existent epochs_id or time column in the epochs table"""

    def __init__(self, mkh5_f, epochs_name, col):
        msg = f"{mkh5_f} epochs table {epochs_name} column error {col}, check {epochs_name}.columns"
        self.args = (msg,)


class EpochsMkh5NonZeroTimestamps(ValueError):
    """raised if values in the the specified mkh5 timestamp column vary or differ from the timelock=value"""

    def __init__(self, mkh5_f, epochs_name, col):
        msg = (
            f"{mkh5_f} epochs table {epochs_name} time column {col} has non-zero timestamps. "
            f"MNE epochs, (tmin, tmax) are defined relative to the timelock event at time=0."
            f"Inspect the epochs table in {mkh5_f} with mkh5.mkh5.get_epochs_table({epochs_name}) "
            f"to locate the discrepant timestamps. If the mkh5 event table is overgenerating "
            f"match_time events with non-zero time-stamps, prune the rows with non-zero timesamps "
            f"in {col}, and set the epochs with the new event table mkh5.mkh5.set_epochs(event_table)."
        )
        self.args = (msg,)


# ------------------------------------------------------------
# Apparatus YAML file


class ApparatusYamlFileError(Exception):
    """yaml file didn't open for any reason"""

    def __init__(self, msg):
        self.args = (f"{msg} check file name, path, and permissions",)


# ------------------------------------------------------------
# MNE structure exceptions
class Mkh5DblockInfoMismatch(Exception):
    """raised if MNE info structures differ, e.g., across mkh5 dblocks"""

    def __init__(self, msg_1, msg_2):
        self.args = (msg_1 + "\n" + msg_2,)


class Mkh5DblockMontageMismatch(Exception):
    """raised if MNE montage structures differ, e.g., across mkh5 dblocks"""

    def __init__(self, msg_1, msg_2):
        self.args = (msg_1 + "\n" + msg_2,)


# ------------------------------------------------------------
# private-ish helpers
def _check_package_versions():
    """ guard the MNE and mkh5 version for compatible header -> info, montage"""

    ver_re = re.compile(r"^(?P<M>\d+)\.(?P<N>\d+)\.(?P<P>){0,1}.*$")

    mne_ver = ver_re.match(mne.__version__)
    assert mne_ver is not None
    if int(mne_ver["M"]) < MNE_MIN_VER[0] and int(mne_ver["N"]) < MNE_MIN_VER[1]:
        msg = f"MNE {mne.__version__} must be >= {' '.join(MNE_MIN_VER)}"
        raise NotImplementedError(msg)

    mkh5_ver = ver_re.match(mkh5.__version__)
    assert mkh5_ver is not None
    if (
        int(mkh5_ver["M"]) < MKH5_MIN_VER[0]
        and int(mkh5_ver["N"]) < MKH5_MIN_VER[1]
        and int(mkh5_ver["P"]) < MKH5_MIN_VER[2]
    ):
        msg = (
            f"mkpy.mkh5 version {mkh5.__version__} must be "
            f">= {' '.join(MKH5_MIN_VER)}"
        )
        raise NotImplementedError(msg)


def _check_api_params(_class, mkh5_f, **kwargs):
    """screen mkh5_f, dblock paths and epoch names prior to processing

    _obj_clas == Raw, Epochs

    Parameters
    ----------
    _class : RawMkh5

    mkh5_f : str
        path to mkh5 file

    **kwargs
        see module KEYWARGS

    """
    # mne and mkh5
    _check_package_versions()

    # API feeds parameters to the classes, user actions cannot
    # make the assertions fail
    # assert _class in [RawMkh5, EpochsMkh5], \
    assert _class is RawMkh5, "_check_api_params _class must be RawMkh5"

    # set the module kwargs for the input class RawMkh5 or EpochsMkh5
    module_kwargs = KWARGS
    # if _class == EpochsMkh5:
    #     module_kwargs.update(**EPOCHS_KWARGS)

    # screen input for illegal keys
    for key in kwargs.keys():
        if key not in module_kwargs:
            raise ValueError(f"unknown keyword '{key}' in {key}={kwargs[key]}")

    # fill in missing keyword params, if any, with module defaults
    for key, val in module_kwargs.items():
        if key not in kwargs.keys():
            kwargs[key] = val

    # ------------------------------------------------------------
    # now have a full set of module kwargs with input values or defaults

    # arg: mkh5 file check
    if not Path(mkh5_f).exists():
        msg = f"cannot open {mkh5_f} check file name, path, and permissions"
        raise Mkh5FileAccessError(msg)

    # ------------------------------------------------------------
    # verbose
    verbose = kwargs["verbose"]
    if verbose not in VERBOSE_LEVELS:
        msg = f"verbose={verbose} level must be: {' '.join(VERBOSE_LEVELS)}"
        raise ValueError(msg)

    # ------------------------------------------------------------
    # e.g., dblock_paths=["group/dblock_0", "group/dblock_1", ...]  or all
    assert kwargs["dblock_paths"] is not None, "set dblock_paths=[...], else very slow"
    dblock_paths = kwargs["dblock_paths"]

    if not (
        isinstance(dblock_paths, list)
        and all([isinstance(dbp, str) for dbp in dblock_paths])
    ):
        msg = f"dblock_paths={dblock_paths} must be a list of strings"
        raise TypeError(msg)

    # ------------------------------------------------------------
    # e.g., garv_interval=[-500, 1500, "ms"]
    garv_interval = kwargs["garv_interval"]
    if garv_interval:
        garv_start, garv_stop, garv_unit = garv_interval
        if garv_unit not in ["ms", "s"]:
            msg = f"garv_unit={garv_unit} must be 'ms' or 's"
            raise ValueError(msg)

        t_scale = 1000.0 if garv_unit == "ms" else 1.0

        # let python raise TypeError for non-numerical values
        garv_start /= t_scale
        garv_stop /= t_scale

        if not garv_start < garv_stop:
            msg = f"garv_start={garv_start} must be < garv_stop={garv_stop}"
            raise ValueError(msg)

    # info and montage toggles
    for key in ["fail_on_info", "fail_on_montage"]:
        assert key in kwargs.keys()
        if not isinstance(kwargs[key], bool):
            raise TypeError(f"{key}={kwargs[key]} must be True or False")

        # turning off montage checking for epochs is risky
        if kwargs["fail_on_montage"] is False:
            msg = (
                "setting fail_on_montage=False disables MNE montage "
                "verification accross mkh5 data blocks, the MNE sensor "
                "locations may be wrong and MNE epoch conversion may fail"
            )
            warnings.warn(msg)

    # ------------------------------------------------------------
    # optional apparatus yaml
    if kwargs["apparatus_yaml"] is not None:
        apparatus_yaml = kwargs["apparatus_yaml"]
        try:
            open(apparatus_yaml)
        except Exception as fail:
            raise ApparatusYamlFileError(str(fail))

    if kwargs["ignore_keys"] is not []:
        ignore_keys = kwargs["ignore_keys"]
        try:
            for key in ignore_keys:
                if not isinstance(key, str):
                    msg = f"ignore_keys must be a list of strings, not {ignore_keys}"
                    raise ValueError(msg)
        except Exception as fail:
            raise fail

    # ------------------------------------------------------------
    # # DEPRECATE? EpochsMkh5 kwargs
    # if _class == EpochsMkh5:

    #     epochs_name = kwargs["epochs_name"]

    #     # catches non-strings including epochs_name=None
    #     if not isinstance(epochs_name, str):
    #         msg = f"epochs_name={epochs_name} must be a character string"
    #         raise TypeError(msg)

    #     # check the epochs table h5 object exists
    #     if epochs_name not in h5.epochs_names:
    #         raise EpochsMkh5EpochsNameError(mkh5_f, epochs_name)

    #     # ok to set column names here
    #     epochs_table = h5.get_epochs_table(epochs_name)

    #     # shouldn't fail unless the the mkh5 file is tampered with
    #     assert all([dbp in all_dblock_paths for dbp in epochs_table.dblock_path])

    #     # check epochs_id, time cols exist
    #     for test_param in ["epoch_id", "time"]:
    #         col_name = kwargs[test_param]
    #         try:
    #             epochs_table[col_name]
    #         except Exception:
    #             raise EpochsMkh5ColumnNameError(mkh5_f, epochs_name, col_name)

    #     # this value is critical for correctly cacluating the
    #     # MNE fixed-interval epoch with tmin, tmax
    #     if not all(epochs_table[kwargs["time"]] == 0):
    #         raise EpochsMkh5NonZeroTimestamps(mkh5, epochs_name)

    # full set of checked kwargs for _class RawMkh5 or EpochsMkh5
    return kwargs


def _is_equal_mne_info(info_a, info_b, exclude=[], verbose=False):
    """compare two mne.Info key, value instances for same content

    Parameters
    ----------
    info_a, info_b : mne.Info
       as instantiated, e.g., by mne.create_info(...)

    exclude : list of str, optional
       list of mne.Info.keys() to skip when testing, e.g. "meas_id",
       "file_id" which change file_id timestamps with .fif saves.

    Returns
    -------
    bool:
       True if info structure contets are the same to within
       floating-point precision, False otherwise.

    Notes
    -----
    verbose=True reports the key, values that differ.
    """

    test_keys_a = [key for key in info_a.keys() if key not in exclude]
    test_keys_b = [key for key in info_b.keys() if key not in exclude]
    if not set(test_keys_a) == set(test_keys_b):
        raise KeyError("info_a and info_b have different keys")

    # collect bad keys for verbose reporting
    good_keys = list()  # whitelist the values that test the same
    bad_keys = list()  # blacklist mismatches
    for key in test_keys_a:
        val_a = info_a[key]
        val_b = info_b[key]

        # most info values hash test fine
        if object_hash(val_a) == object_hash(val_b):
            good_keys.append(key)

        # dig and chan need special handling
        elif key in "dig":
            try:
                assert val_a == val_b
                good_keys.append(key)
            except Exception:
                bad_keys.append(key)
        elif key in ["chs"]:
            # assert all vals are equal or close,
            try:
                for chdx, ch_a in enumerate(val_a):
                    ch_b = val_b[chdx]
                    for key_aa, val_aa in ch_a.items():
                        val_bb = ch_b[key_aa]
                        #  np.allclose b.c. .fif save float precision may
                        # tinker with info["chs"][i]["loc"] values
                        assert object_hash(val_bb) == object_hash(
                            val_aa
                        ) or np.allclose(val_aa, val_bb)
                good_keys.append(key)
            except Exception:
                bad_keys.append(key)
        else:
            bad_keys.append(key)

    # print(f"good_keys {good_keys} excluded {exclude}")
    if sorted(good_keys) == sorted(test_keys_a) == sorted(test_keys_b):
        return True
    else:
        if verbose:
            for key in bad_keys:
                print(f"info_a['{key}']: {info_a[key]}")
                print(f"info_b['{key}']: {info_b[key]}")
                print()
        return False


def _is_equal_mne_montage(montage_a, montage_b, verbose="info"):
    """ compare two mne montages for identity"""

    # fall through for msgs when verbose=True
    attrs_a = sorted(montage_a.__dict__.keys())
    attrs_b = sorted(montage_b.__dict__.keys())

    if not attrs_a == attrs_b:
        if verbose:
            msg = f"montage attributes differ: {attrs_a} {attrs_b}"
            print(msg)
        return False

    # report the mismatches
    for attr in attrs_a:
        val_a = getattr(montage_a, attr)
        val_b = getattr(montage_b, attr)
        if val_a != val_b:
            print(f"mismatch {attr} {val_a} != {val_b}")
            return False
    return True


def _check_info_montage_across_dblocks(mkh5_f, ignore_keys=[], **kwargs):
    """check hdr, dblocks in mkh5_f return the same MNE info and montage

    The default behavior for info mismatches is to issue a warning
    since discrepant structures arise whenever multiple crws are
    combined in a single mkh5 file, e.g., for separate cal files, split
    sessions, and multi-subject experiment files.

    The default behavior for montage mismatches is to fail since there
    are very few cases in which it is reasonable to pool data data
    recorded from different montages in a single analysis. Montages
    that very across datablocks in an mkh5 file are most likely
    attributable to using discrepant .yhdr apparatus maps when the
    mkh5 file was converted from .crw/.log. In this case the remedy is
    to correct the .yhdr files and rebuild the mkh5 file.  Montage
    differences make MNE spatial visualization and data analysis
    unreliable and montage failures should be allowed with extreme
    caution in unusual circumstances.

    Parameters
    ----------
    mkh5_f: str
        file path to mkpy.mkh5 file
    ignore_keys : list of str {[]}
        differences between the values of these info keys are ignored even
        when fail_on_info=True, see IGNORE_INFO_KEYS.
    dblock_paths: {list of str, None}, optional
        as returned by mkh5.mkh5(mkh5_f).dblock_paths
        do not check the keys in the list, the default values
        typically vary across mkh5 dblocks
    apparatus_yaml: str
        file path to a YAML file containing exactly one mkpy.mkh5
        apparatus format YAML doc, such as a .yhdr
    fail_on_info: bool {False}, optional
        whether to fail on mismatching MNE info structures,
        default=False
    fail_on_montage: bool {True}, optional
        whether to fail on mismatching MNE montage structures,
        default=True
    verbose: str {"info", "critical", "error", "warning", "debug", "notset"}
        level of python logging reporting

    """

    # clunky but clear ...
    dblock_paths = kwargs["dblock_paths"]
    apparatus_yaml = kwargs["apparatus_yaml"]
    fail_on_info = kwargs["fail_on_info"]
    fail_on_montage = kwargs["fail_on_montage"]
    verbose = kwargs["verbose"]

    if fail_on_info:
        verbose = "info"  # fail informatively

    h5 = mkh5.mkh5(mkh5_f)

    # enforce explicit dblock_paths kwarg
    assert dblock_paths is not None, "set dblock_paths kwarg, else too slow"

    # check pairwise against first
    dbp_i = dblock_paths[0]
    hdr_i, dblock_i = h5.get_dblock(dbp_i)
    info_i, montage_i = _hdr_dblock_to_info_montage(
        hdr_i, dblock_i, apparatus_yaml=apparatus_yaml
    )

    for dbp_j in dblock_paths[1:]:

        print(f"checking info, montage {dbp_j}")

        hdr_j, dblock_j = h5.get_dblock(dbp_j)
        info_j, montage_j = _hdr_dblock_to_info_montage(
            hdr_j, dblock_j, apparatus_yaml=apparatus_yaml
        )
        # info
        if not _is_equal_mne_info(info_i, info_j, exclude=ignore_keys):
            if fail_on_info:
                raise Mkh5DblockInfoMismatch(str(info_i), str(info_j))
            else:
                msg = f"MNE info differs: {dbp_i} {dbp_j}"
                if verbose:
                    msg += f": {str(info_i)} != {str(info_j)}"
                warnings.warn(msg)

        # montage
        if not _is_equal_mne_montage(montage_i, montage_j):
            if fail_on_montage:
                raise Mkh5DblockMontageMismatch(str(montage_i), str(montage_j))
            else:
                msg = f"MNE montages differ: {dbp_i} {dbp_j}"
                if verbose:
                    msg += f": {str(montage_i)} != {str(montage_j)}"
                warnings.warn(msg)


class RawMkh5(mne.io.BaseRaw):
    """Raw MNE compatible object from mkpy.mkh5 HDF5 data file

    Parameters
    ----------
    mkh5_f : str
        file path to existing mkpy.mkh5 data file 0.2.4+

    Notes
    -----
    We maintain dblock -> RawArray and let MNE handle the
    bookeeping for knitting RawArrays together. Not future
    proof but perhaps more future resistant.

"""

    def __init__(
        self,
        mkh5_f,
        garv_interval=None,
        dblock_paths=None,
        fail_on_info=False,
        fail_on_montage=True,
        apparatus_yaml=None,
        verbose="info",
        ignore_keys=IGNORE_INFO_KEYS,
    ):

        if dblock_paths is None:
            print(mkh5_f)
            print("looking up data block paths, larger files take longer ...")
            dblock_paths = mkh5.mkh5(mkh5_f).dblock_paths
        print("ok")

        _kwargs = _check_api_params(
            RawMkh5,
            mkh5_f,
            dblock_paths=dblock_paths,
            garv_interval=garv_interval,
            fail_on_info=fail_on_info,
            fail_on_montage=fail_on_montage,
            apparatus_yaml=apparatus_yaml,
            verbose=verbose,
            ignore_keys=ignore_keys,
        )
        _check_info_montage_across_dblocks(mkh5_f, **_kwargs)

        raw_dblocks = []
        mne_ditis = dict()
        raw_samp_n = 0  # track accumulated samples across data blocks
        for dbpi, dbp in enumerate(dblock_paths):

            # raw_dblock is an instance of mne.Raw, db_epts is a dic with keys in
            # epoch_names and vals = the mkh5 epochs table dataframe row sliced
            # for this data block path.
            raw_dblock, db_epts = _dblock_to_raw(
                mkh5_f, dbp, garv_interval, apparatus_yaml
            )
            # the data
            raw_dblocks.append(raw_dblock)

            # reassemble mkh5 epochs_tables
            for key, val in db_epts.items():

                diti = val.copy()  # pd.DataFrame.copy()

                assert all(diti["dblock_path"] == dbp)
                diti["mne_dblock_path_idx"] = dbpi

                # compute sample index into the mne.Raw data stream from the
                # the length thus far + dblock_tick offset (0-base)
                diti["mne_raw_ticks"] = raw_samp_n + diti["dblock_ticks"]
                if key not in mne_ditis.keys():
                    # start a new table w/ mne raw ticks counting from 0
                    mne_ditis[key] = diti
                else:
                    # continue an existing table
                    assert all(mne_ditis[key].columns == diti.columns)
                    mne_ditis[key] = mne_ditis[key].append(diti)
            raw_samp_n += len(raw_dblock)

        # assemble
        mne_raw = mne.io.concatenate_raws(raw_dblocks, preload=True)
        info = deepcopy(mne_raw.info)

        # convert epochs table dataframes to dicts for JSONification
        for epochs_name, epochs_table in mne_ditis.items():
            mne_ditis[epochs_name] = epochs_table.to_dict()

        # really belongs attached to the raw, e.g., raw._ditis map of ditis
        info["description"] = json.dumps({"mkh5_epoch_tables": mne_ditis})

        # event and eeg datastreams numpy array
        data = mne_raw.get_data()
        super().__init__(
            info=info,
            preload=data,
            filenames=[mkh5_f],
            # orig_format='single',
        )

        # collect boundaries, log_evcodes, and optional garv intervals
        # marked by concatenate_raw
        self.set_annotations(mne_raw.annotations)

        # or average?
        self.set_eeg_reference(
            ref_channels=[], projection=False, ch_type="eeg"  # "average"
        )


# ------------------------------------------------------------
# file loader for optional apparatus yaml
def _load_apparatus_yaml(apparatus_yaml_f):
    """slurp apparatus info and return the dict or die

    The file is screened for a unique YAML doc with name: apparatus

    Parameters
    ----------
    apparatus_yaml_f: str
        filepath to yaml

    Returns
    -------
    dict
       contains name: apparatus, contents are validated as for
       native mkh5 header apparatus dict
    """

    with open(apparatus_yaml_f) as apparatus_stream:
        yaml_docs = list(yaml.safe_load_all(apparatus_stream))
        apparatus_hdrs = [
            yaml_doc
            for yaml_doc in yaml_docs
            if dpath.util.search(yaml_doc, "name") == {"name": "apparatus"}
        ]

        msg = None
        if len(apparatus_hdrs) == 0:
            msg = f"no apparatus document"
        if len(apparatus_hdrs) > 1:
            msg = f"multiple apparatus documents"

        if msg:
            msg += (
                f" in {apparatus_yaml_f}, there must be exactly one "
                "YAML doc with name: apparatus"
            )
            raise Mkh5HeaderValueError(msg)

    return yaml_docs[0]


# ------------------------------------------------------------
# .yhdr header functions used by RawMkh5 and EpochsMkh5
def _validate_hdr_for_mne(hdr):
    """check the mkh5 header key: vals for _parse_header_for_mne

    Exception messages report the data block, missing keys and
    wrong values.

    Parameters
    ----------
    hdr : dict
       mkpy.mkh5 dblock header as returned by mkh5.get_dblock()

    Raises
    ------
    Mkh5HeaderKeyError
       if header is missing a key needed for MNE import
    Mkh5HeaderValueError
       if value is wrong for MNE import
     Notes
    -----

    Required Keys

      FIXME
       The header must have
         h5_dataset: <str> samplerate: <int|float> and and apparatus: <map>
       The apparatus must have these maps: common_ref: <str>, space: <map>, fiducials: <map>, streams, sensors
       The apparatus streams must have mne_type: <str> pos: <str> neg: <str>
       The apparatus sensors must have x: <float> y: <float> z: <float>

     Required Values
       The h5_dataset string must be a conforming /*/dblock_N mkh5 data block HDF5 path.
       The sample rate must be an inter or float.
       The apparatus streams mne_type must be a legal MNE channel
      type: eeg, eog, stim, misc, ...
       The apparatus streams pos (= sensor/electrode on +pinout of
      bioamp) must be one of the apparatus sensor keys to provide
      the 3D coordinates.
       The apparatus sensor coordinates must be numeric.
     """

    # ------------------------------------------------------------
    # these key: vals are built in by mkh5, check anyway
    if "h5_dataset" not in hdr.keys():
        msg = f"header is missing required key: h5_dataset"
        raise Mkh5HeaderKeyError(msg)

    dblock_path_re = re.compile(r"^/(\w+/)+(dblock_\d+){1}$")
    if dblock_path_re.match(hdr["h5_dataset"]) is None:
        msg = (
            "header h5_dataset is not a mkpy.mkh5 data block path "
            f"/*/dblock: {hdr['h5_dataset']}"
        )
        raise Mkh5HeaderValueError(msg)

    # used for error messages
    dblock_path = hdr["h5_dataset"]

    # ------------------------------------------------------------
    # header must have a samplerate
    if "samplerate" not in hdr.keys():
        msg = f"header has no samplerate key"
        raise Mkh5HeaderKeyError(msg, dblock_path)

    if not isinstance(hdr["samplerate"], (int, float)):
        msg = f"header samplerate must be numeric (integer or float)"
        # sub_hdr = {"samplerate": hdr["samplerate"]}
        sub_hdr = dpath.search("hdr", "samplerate")
        raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)

    sfreq = hdr["samplerate"]

    # ------------------------------------------------------------
    # these key: vals are user specified YAML, anything can happen.

    # there must be an apparatus map
    if "apparatus" not in hdr.keys():
        msg = f"apparatus map not found"
        raise Mkh5HeaderKeyError(msg, dblock_path)

    # ------------------------------------------------------------
    # apparatus must have stream, sensor, fiducial, common_ref  maps
    for key in ["streams", "sensors", "fiducials", "common_ref", "space"]:
        if key not in hdr["apparatus"]:
            msg = f"apparatus {key} map not found"
            raise Mkh5HeaderKeyError(msg, dblock_path)

    # ------------------------------------------------------------
    space = {"coordinates": "cartesian", "distance_unit": "cm", "orientation": "ras"}
    hdr_space = dpath.util.values(hdr, "apparatus/space")[0]
    for key in space.keys():
        if key not in hdr_space.keys():
            msg = f"apparatus space map must include {key}: {space[key]}"
            raise Mkh5HeaderKeyError(msg, dblock_path)

        if not hdr_space[key] == space[key]:
            msg = f"apparatus space map must include {key}: {space[key]}"
            raise Mkh5HeaderValueError(msg, dblock_path, hdr_space)

    # ------------------------------------------------------------
    # collect sensor/electrode labels, these vary by experiment
    hdr_sensors = list(hdr["apparatus"]["sensors"].keys())

    # common reference electrode must be among known sensors
    if hdr["apparatus"]["common_ref"] not in hdr_sensors:
        sub_hdr = dpath.util.search(hdr, "/apparatus/common_ref")
        msg = (
            f"apparatus common_ref value must"
            f"be one of these: <{'|'.join(hdr_sensors)}>"
        )
        raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)

    # ------------------------------------------------------------
    # check string values
    HDR_MNE_STREAM_KEY_VALS = {
        "mne_type": MNE_STREAM_TYPES,  # eeg, eog, stim, misc, ...
        "pos": hdr_sensors,  # these provide the 3D coordinates
        "neg": hdr_sensors,  # these provide the 3D coordinates
    }

    for stream, val in hdr["apparatus"]["streams"].items():

        sub_hdr = dpath.util.search(hdr, f"apparatus/streams/{stream}")

        # check the mne_type, pos, neg keys
        for key in HDR_MNE_STREAM_KEY_VALS.keys():
            if key not in val.keys():
                msg = f"apparatus stream {key} not found"
                raise Mkh5HeaderKeyError(msg, dblock_path, sub_hdr)

        # check the values
        for key, vals in HDR_MNE_STREAM_KEY_VALS.items():
            if not val[key] in vals:
                msg = (
                    f"apparatus stream {stream} {key} value must"
                    f"be one of these: <{'|'.join(vals)}>"
                )
                raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)

    # ------------------------------------------------------------
    # fiducial keys are lpa, rpa, nasion
    FID_KEYS = ["lpa", "rpa", "nasion"]
    for fid_key in FID_KEYS:
        if fid_key not in hdr["apparatus"]["fiducials"].keys():
            sub_hdr = dpath.util.search(hdr, "apparatus/fiducials")
            msg = (
                f"apparatus fiducials (lpa, rpa, nasion) location "
                "{fid_key} not found"
            )
            raise Mkh5HeaderKeyError(msg, dblock_path, sub_hdr)

    # ------------------------------------------------------------
    # sensors and fiducials  must have 3D x, y, z keys and numeric values
    for key_3d in ["sensors", "fiducials"]:
        for key, val in hdr["apparatus"][key_3d].items():
            # sub_hdr = {"apparatus": {key_3d: {key: val}}}
            sub_hdr = dpath.util.search(hdr, f"apparatus/{key_3d}/{key}")
            for axis in ["x", "y", "z"]:
                if axis not in val.keys():
                    msg = (
                        f"apparatus {key_3d} {key} 3D x,y,z "
                        f"coordinate axis {axis} not found"
                    )
                    raise Mkh5HeaderKeyError(msg, dblock_path, sub_hdr)

                if not isinstance(val[axis], (int, float)):
                    msg = (
                        f"apparatus {key_3d} {key} coordinate "
                        f"{axis} must be a numeric value"
                    )
                    raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)


def _parse_hdr_for_mne(hdr, dblock, apparatus_yaml=None):
    """return header info formatted for MNE dig montage and info

    The user-specified hdr["apparatus"]["streams]["mne_type"] values from the
    the YAML .yhdr are used, all the rest of the data block columns are
    assigned MNE type "misc"

    Parameters:
    -----------
    hdr : dict
       as returned hdr, dblock = ``mkh5.get_dblock()``

    dblock : np.ndarray
       as returned hdr, dblock = ``mkh5.get_dblock()``

    apparatus_yaml : {None, str}, optional
       filepath to YAML file alternate stream and sensor information.
       Format requirements are the same as for the mkh5 header

    Returns
    -------
    results: dict
        keys, values for MNE montage, create_info, and
         set_eeg_reference methods `sfreq`, `set_ref_ch_type`,
         `set_ref_channels`, `ch_labels`, `ch_types`, `dig_ch_pos`


    Notes
    -----

    Validation is done in _validate_hdr_for_mne, this just collects
    and formats the header data.

    """

    # cm distance units are guarded in _validate_hdr_for_mne
    YHDR_RAS_UNIT = 0.01

    # ------------------------------------------------------------
    # apparatus streams are user YAML w/ mne_type, typically
    # a subset of the hdr["streams"] which includes clock ticks,
    # and events

    # optionally update native mkh5 hdr apparatus
    if apparatus_yaml is not None:
        hdr["apparatus"] = _load_apparatus_yaml(apparatus_yaml)
        msg = (
            f"Overriding {hdr['h5_dataset']} with sensor locations"
            f" from {apparatus_yaml}"
        )
        warnings.warn(msg)

    _validate_hdr_for_mne(hdr)

    apparatus_streams = pd.DataFrame.from_dict(
        hdr["apparatus"]["streams"], orient="index"
    ).rename_axis(index="stream")

    # sensors (=electrodes) are physical objects in 3-space
    apparatus_sensors = pd.DataFrame.from_dict(
        hdr["apparatus"]["sensors"], orient="index"
    ).rename_axis(index="pos")

    # sinnce eeg data streams don't have a "location" use
    # coordinates from the positive pinout electrode
    apparatus_streams = apparatus_streams.join(apparatus_sensors, how="left", on="pos")

    # collect the fiducials
    apparatus_fiducials = pd.DataFrame.from_dict(
        hdr["apparatus"]["fiducials"], orient="index"
    ).rename_axis(index="fiducial")

    # ------------------------------------------------------------
    # collect the mkpy.mkh5 built-in data block hdr["streams"],
    hdr_streams = pd.DataFrame.from_dict(hdr["streams"], orient="index").rename_axis(
        index="stream"
    )

    # mkh5 built-in hdr["streams"] align 1-1 with
    # the dblock data 1-D columns unless tampered with
    # assert tuple(hdr_streams.index) == dblock.dtype.names

    # merge in the apparatus stream data
    hdr_streams = hdr_streams.join(apparatus_streams, how="left", on="stream")

    # update known dblock streams to mne_types
    hdr_streams.loc[["raw_evcodes", "log_evcodes", "log_ccodes"], "mne_type"] = "stim"
    hdr_streams.loc[pd.isna(hdr_streams["mne_type"]), "mne_type"] = "misc"

    # 3D sensor coordinate cm  dicts -> in MNE key: [R, A, S, ... ] m format
    # fiducial landmarks in MNE label: [x, y, z] format
    fiducials = apparatus_fiducials.apply(
        lambda row: row.to_numpy(dtype=float) * YHDR_RAS_UNIT, axis=1
    ).to_dict()

    # for mne.channels.make_dig_montage
    dig_ch_pos = apparatus_streams.apply(
        lambda row: row[["x", "y", "z"]].to_numpy(dtype=float) * YHDR_RAS_UNIT, axis=1
    ).to_dict()

    # for info["chs"][i]["loc"] = array, shape(12,)
    # first 3 are positive sensor, next 3 are reference (negative)
    # but MNE DigMontage chokes on mixed common ref (A1) and biploar
    # so skip the reference location
    info_ch_locs = {}
    for ch, row in apparatus_streams.iterrows():
        # e.g., A1 for common reference, lhz for bipolar HEOG.
        pos = apparatus_streams.loc[ch, "pos"]
        # neg = apparatus_streams.loc[ch, "neg"]   # not used
        pos_locs = apparatus_sensors.loc[pos, :]
        info_ch_locs[ch] = (
            np.hstack(
                # [pos_locs, ref_locs, np.zeros((6, ))] # the truth
                [pos_locs, np.zeros((9,))]  # what works w/ MNE
            )
            * YHDR_RAS_UNIT
        )

    result = dict(
        sfreq=hdr["samplerate"],
        set_ref_ch_type="eeg",
        set_ref_channels=hdr["apparatus"]["common_ref"],
        ch_labels=hdr_streams.index.to_list(),
        ch_types=hdr_streams.mne_type,
        dig_ch_pos=dig_ch_pos,
        info_ch_locs=info_ch_locs,
    )
    result.update(fiducials)
    return result


def _patch_dblock_info(info, hdr, hdr_mne):
    """tune up MNE info with additional mkpy hdr data

    Most MNE internal values are already set to correct
    values by create_info and ch_types.

    ch_info["cal"] is the critical the scaling factor, so that RawArray
    data * ch_info["cal"] is on the FIFF.FIFF_UNIT_V scale, i.e., 1e-6
    for the calibrated mkpy.mkh5 to microvolts
    """

    # info["proj_name"] = hdr["expdesc"]
    info["subject_info"] = {"his_id": hdr["uuid"]}
    info["device_info"] = {"type": hdr["name"]}

    # dev note:
    # the mne.io.get_new_fileid(), thefile_id == meas_id looks like this
    # {
    #     'machid': array([808661043, 808661043], dtype=int32),
    #     'version': 65540 (FIFFC_VERSION),
    #     'secs': 1601769754,
    #     'usecs': 514806
    # }

    # from mkh5 os.stat_result
    dtime = hdr["eeg_file_stat"]["st_ctime"]

    # seed MNE info fields w/ default and update w/ mkh5 datetimes
    file_id = mne.io.write.get_new_file_id()
    file_id["secs"] = int(dtime)
    file_id["usecs"] = round((dtime % 1) * 10e6)

    info["meas_date"] = datetime.fromtimestamp(dtime, timezone.utc)
    info["meas_id"] = file_id
    info["file_id"] = info["meas_id"]

    # CRITICAL: set scaling factor for microvolt data
    for idx, ch_info in enumerate(info["chs"]):
        ch_name = ch_info["ch_name"]
        is_eeg = ch_info["kind"] == FIFF.FIFFV_EEG_CH
        is_eog = ch_info["kind"] == FIFF.FIFFV_EOG_CH
        if is_eeg or is_eog:

            # update ch locs from parsed hdr["apparatus"]["sensor"]
            ch_info["loc"] = hdr_mne["info_ch_locs"][ch_name]

            # from create_info
            assert ch_info["unit"] == FIFF.FIFF_UNIT_V

            # CRITICAL this scales mkh5 calibrated uV to MNE V
            ch_info["cal"] = 1e-6

            # mkh5 data blocks may or may not be calibrated
            if not (
                "calibrated" in hdr["streams"][ch_name].keys()
                and hdr["streams"][ch_name]["calibrated"]
            ):
                msg = (
                    f"mkh5 data {hdr['h5_dataset']} {ch_name} "
                    "is not calibrated, scale is unknown"
                )
                warnings.warn(msg)

    return info


# def _check_header_across_dblocks(mkh5_f):
#     """return headers checked for same streams and apparatus across data blocks

#     Parameters
#     ----------
#     mkh5_f : str
#         path to an mkh5 file

#     Returns
#     -------
#     hdrs : dict
#         The keys are `dblock_path` (str) as returned in the list of
#         `mkh5.dblock_paths`. The values are `hdr` (dict) as returned
#         by hdr, dblock = mkh5.get_dblock().


#     Raises
#     ------
#     Mkh5HeaderError

#     """

#     h5 = mkh5.mkh5(mkh5_f)
#     dblock_paths = h5.dblock_paths
#     hdrs = []
#     mismatch = None
#     for dblock_path in dblock_paths:
#         hdr, _ = h5.get_dblock(dblock_path)
#         _validate_hdr_for_mne(hdr)

#         # identity is transitive, checking ith vs. first suffices
#         if len(hdrs) > 0:
#             if not hdr["streams"].keys() == hdrs[0]["streams"].keys():
#                 mismatch = "stream"
#             if not hdr["apparatus"] == hdrs[0]["apparatus"]:
#                 mismatch = "apparatus"
#             if mismatch:
#                 msg = (
#                     f"data block header mismatch header['{mismatch}'] "
#                     f"{dblock_paths[0]} {dblock_path}"
#                 )
#                 raise Mkh5HeaderError(msg)
#         hdrs.append(hdr)
#     return dict(zip(dblock_paths, hdrs))


# ------------------------------------------------------------
# general data wrangling
def _dblock_to_raw(mkh5_f, dblock_path, garv_interval=None, apparatus_yaml=None):
    """convert one mkh5 datablock+header into one mne.RawArray

    Ingest one mkh5 format data block and return an mne.RawArray
    populated with enough data and channel information to use mne.viz
    and the mne.Epochs, mne.Evoked EEG pipeline.

    Parameters
    ----------
    dblock_path : str
       HDF5 slash path to an mkh5 data block which an h5py.Dataset
    garv_interval: iterable of two numbers
       interval in milliseconds relative to a log_evcode event at time==0
    apparatus_yaml: str, optional
       filepath to YAML apparatus file with stream and sensor space info
       to override native mkh5 hdr["apparatus"] if any. 

    Returns
    -------
    mne.RawArray
        with channel locations from apparatus_yaml and mkh5 epochs tables
        JSONified and tucked into the Info["description"]

    Notes
    -----

    The raw_dblock returned from this can be stacked with
    mne.concatenate_raws() though MNE behavior is to use first
    info and just stack the datablocks. epochs metadata is
    collected and returned per block so the complete record
    can be tucked into the (one) info object when the dblocks
    are stacked. 

    The  raw.set_eeg_reference(ref_channels=[]) at the end to block
    subsequent mne's default automatic average rereferencing later in
    the pipeline (sheesh).

    """
    h5 = mkh5.mkh5(mkh5_f)
    try:
        hdr, dblock = h5.get_dblock(dblock_path)
    except Exception as fail:
        raise Mkh5DblockPathError(str(fail), mkh5_f, dblock_path)

    info, montage = _hdr_dblock_to_info_montage(
        hdr, dblock, apparatus_yaml=apparatus_yaml
    )

    # mne wants homogenous n_chans x nsamps, so stim, misc ints coerced
    # to float ... sigh.
    mne_data = np.ndarray(shape=(len(dblock.dtype.names), len(dblock)), dtype="f8")

    # slice out and scale mkh5 recorded data to mne standards
    for jdx, stream in enumerate(dblock.dtype.names):
        assert info["ch_names"][jdx] == stream
        mne_data[jdx] = dblock[stream] * info["chs"][jdx]["cal"]

    # create the raw object
    raw_dblock = mne.io.RawArray(mne_data, info, copy="both")
    raw_dblock.set_montage(montage)

    # ------------------------------------------------------------
    # add an MNE data column for each epochs_table in the mkh5 file
    #   - for each one, slice the timelock events at match_time == 0
    #   - copy the time-locked event code to the epochs column and
    #     the rest of the epochs tables columns to metadata.

    epochs_table_names = mkh5.mkh5(mkh5_f).get_epochs_table_names()
    epochs_table_descr = dict()  # returned for mkh5 epoching from MNE Raw

    log_evcodes, _ = raw_dblock["log_evcodes"]  # for checking
    if len(epochs_table_names) > 0:
        for etn in epochs_table_names:

            # fetch the epochs_table and slice for this mkh5 data block
            print(f"{dblock_path} setting mkh5 epochs table {etn} events and metadata")
            epochs_table = h5.get_epochs_table(etn)
            etn_dblock = (
                epochs_table.query("dblock_path == @dblock_path and match_time==0")
            ).copy()

            # CRITICAL: The mkh5 epoch table indexes HDF5 data by
            # dblock_path, dblock_tick (row offset), the row sort
            # order is undefined. MNE squawks if event array
            # sample indexes are not monotonically increasing.
            etn_dblock.sort_values("dblock_ticks", inplace=True)

            # capture epochs table as data frame for later
            epochs_table_descr[etn] = etn_dblock

            # container for the new column of event codes
            etn_evcodes = np.zeros(
                (1, len(raw_dblock)), dtype=raw_dblock.get_data()[0].dtype
            )  # yes, (1, len) b.c. MNE wants chan x time

            # CRITICAL: copy over log_evcodes at just the epoch event ticks
            etn_evcodes[0, etn_dblock.dblock_ticks] = etn_dblock.log_evcodes

            # true by construction of mkh5 epochs. However ...
            assert all(
                log_evcodes[0, etn_dblock.dblock_ticks]
                == etn_evcodes[0, etn_dblock.dblock_ticks]
            )

            # clone the log_evcodes to get their MNE info attributes
            etn_event_channel = raw_dblock.copy().pick(["log_evcodes"])

            # rename and hack in the correct scanno, logno in case it matters
            mne.rename_channels(etn_event_channel.info, {"log_evcodes": etn})
            for field in ["scanno", "logno"]:
                etn_event_channel.info["chs"][0][field] = (
                    raw_dblock.info["chs"][-1][field] + 1
                )

            # set the event code data values append the channel and confirm
            # MNE agrees when asked in its native tongue.
            etn_event_channel._data = etn_evcodes
            raw_dblock.add_channels([etn_event_channel])
            assert all(
                raw_dblock["log_evcodes"][0][0, etn_dblock.dblock_ticks]
                == raw_dblock[etn][0][0, etn_dblock.dblock_ticks]
            )

    # ------------------------------------------------------------
    # seed the MNE annotations with the data block path at time == 0
    raw_dblock.set_annotations(
        mne.Annotations(onset=0.0, duration=0.0, description=dblock_path)
    )

    # add log_evocdes garv annotations, if any. validated in _check_api_params
    if garv_interval:
        bad_garvs = get_garv_bads(raw_dblock, "log_evcodes", garv_interval)
        raw_dblock.set_annotations(raw_dblock.annotations + bad_garvs)

    return raw_dblock, epochs_table_descr


def _hdr_dblock_to_info_montage(hdr, dblock, apparatus_yaml=None):
    """populate MNE structures with mkh5 data"""

    hdr_mne = _parse_hdr_for_mne(hdr, dblock, apparatus_yaml)

    info = mne.create_info(hdr_mne["ch_labels"], hdr_mne["sfreq"], hdr_mne["ch_types"])

    montage = mne.channels.make_dig_montage(
        ch_pos=hdr_mne["dig_ch_pos"],
        nasion=hdr_mne["nasion"],
        lpa=hdr_mne["lpa"],
        rpa=hdr_mne["rpa"],
        coord_frame="head",
    )

    info = _patch_dblock_info(info, hdr, hdr_mne)
    return info, montage


def _check_mne_raw_mkh5_epochs(raw_mkh5, epochs_name):

    hint = (
        " Check that raw_mkh5 = read_raw_mkh5(your_file.h5, ...) and your mkh5 file "
        f"was created with myh5.set_epochs('{epochs_name}', event_table, ...) and a "
        "valid mkh5 format event_table."
    )

    try:
        json_epochs_tables = json.loads(raw_mkh5.info["description"])[
            "mkh5_epochs_tables"
        ]
    except Exception as fail:
        msg = str(fail)
        msg += "could not load raw_mkh5.info['description'] epoch tables JSON data"
        raise ValueError(msg)

    msg = []
    if not any([epochs_name in dbept.keys() for dbept in json_epochs_tables]):
        msg.append(f"raw_mkh5.info does not have any data for {epochs_name} epochs. ")
    elif not all([epochs_name in dbept.keys() for dbept in json_epochs_tables]):
        msg.append(
            f"raw_mkh5.info {epochs_name} data is missing for one or more data blocks. "
        )

    if epochs_name not in raw_mkh5.info["ch_names"]:
        msg.append(
            f"event channel {epochs_name} not found in raw_mkh5.info['ch_names'], "
            "no epoch event information. "
        )

    if not len(msg) == 0:
        msg.append(hint)
        raise ValueError(" ".join(msg))

    return json_epochs_tables


# ------------------------------------------------------------
# API
# ------------------------------------------------------------
def read_raw_mkh5(
    mkh5_file,
    garv_interval=None,
    dblock_paths=None,
    apparatus_yaml=None,
    fail_on_info=False,
    fail_on_montage=True,
    verbose="info",
):

    """Read an mkh5 data file into MNE raw format""

    The mkh5 EEG data, events are converted to mne.BaseRaw for use
    with native MNE methods. The mkh5 timelock events and tags in the
    epochs tables are added to the raw data and mne.Info for use as
    MNE events and metadata with mne.Epochs(raw, events, metadata,
    ...).


    Parameters
    ----------
    mkh5_file: str
        File path to a mkpy.mkh5 HDF5 file

    dblock_paths : {None, list of str}, optional
        Selects dblock_paths and order to concatenate into the
        mne.Raw.  The default is to use all data blocks in the order
        returned by ``mkh5.dblock_paths``.

    garv_interval : list [pre, post, {"ms" | "s"}], optional

        If present, all events on the ``log_evcodes`` data channel are
        bracketed with an MNE annotation in the time interval between
        `pre` to `post` seconds relative to the event with description
        `BAD_garv_N` where N is the integer log_flag code.

    fail_on_info : bool {False}, optional
        If True, this enforces strict mne.Info identity across the
        mkh5 data blocks being concatenated. If False (default), some
        deviations between mne.Info for the mkh5 data blocks are
        allowed, e.g., for pooling multiple subject files into an
        experiment or separate cals for a single subject.

    fail on montage : bool {True}, optional
       If True (default), the mne.Montage created from the mkh5 header
       data streams and channel locations must be the same for all the
       data blocks. If False, the montage may vary across mkh5 data
       blocks; behavior in this case is unpredictable.

    verbose : NotImplemented

    Returns
    -------
    RawMkh5
        subclassed from mne.BaseRaw for use as native MNE.

    Raises
    ------
    Exceptions if data block paths or apparatus map information is
    misspecified or the info and montage test flags are set and fail.


    Notes
    -----

    EEG and events. The mkh5 data block columns are converted to mne
    channels and concatenated into a single mne Raw in the order given
    by `dblock_paths,` the default is to convert the entire mkh5 file
    in `mkh5.dblock_paths` order.

    Epochs. The mkh5 epochs table timelocking events are indexed to
    the mne.Raw data samples and the epoch tables stored as a JSON string
    in mne.Info["description"]. The complete epochs table is recovered
    by JSON loading the ``mne.Info["description"] and converting the
    `epochs_name` dictionary to a pandas.DataFrame. This yields a
    well-formed mne.Epochs.metadata for the events on the
    `epochs_name` stim channel.

    TODO: The mkh5 epochs data, i.e., time-lock events, discrete time
    intervals, and mixed data-type tags would do better as an
    attribute of mne.BaseRaw, e.g., mne.Raw._ditidata. Discrete time
    intervals indexed for (onset, hop, duration) with mixed-type tags
    subsume the spaghetti of MNE events, epochs, and epochs metadata,
    annotations and the discrete time model avoids cumulative rounding
    error issues of floating-point times.

    """
    return RawMkh5(
        mkh5_file,
        garv_interval=garv_interval,
        dblock_paths=dblock_paths,
        fail_on_info=fail_on_info,
        fail_on_montage=fail_on_montage,
        apparatus_yaml=apparatus_yaml,
        verbose=verbose,
    )


def get_garv_bads(mne_raw, event_channel, garv_interval, garv_channel="log_flags"):
    """bracket events with mne BAD_garv annotations

    This timelocks the annotation to all events on event channel that
    have a non-zero codes on the log_flags column, e.g., as given by
    as given by running avg -x -a subNN.arf to set log_flags in
    subNN.log.

    Parameters
    ----------
    mne_raw : mne.Raw
        mne.Raw data object converted from mkh5
    event_channel : str
        name of the mne channel with events to bracket with BAD_garv annotations
    garv_interval : list of [start, stop, unit]
         start and stop are human readable numeric times relative to
         the event, unit is "ms" or "s"
    garv_channel : str, optional
         name of the channel to check for non-zero codes at time-lock
         events. The default="log_flags" is where avg -x puts garv rejects,
         other routines may use other channels.

    Returns
    -------
    mne.Annotations
        formatted as ``BAD_garv_int`` for triggering mne's drop by
        annotation mechanism.

    """

    # modicum of validation
    msg = None
    try:
        garv_start, garv_stop, garv_unit = garv_interval
        if not garv_start < garv_stop:
            raise ValueError("bad interval")
        if garv_unit == "s":
            pass
        elif garv_unit == "ms":
            garv_start /= 1000.0
            garv_stop /= 1000.0
        else:
            raise ValueError("bad units")
    except Exception as fail:
        msg = str(fail)
    if msg:
        msg += (
            "garv_interval=[start, stop, units] with numeric start < stop "
            "and units s or ms"
        )
        raise ValueError(msg)

    garv_duration = garv_stop - garv_start

    # epoch event channel column
    event_ch = mne_raw.get_data(event_channel)[0].astype(int)

    # artifact channel column
    garv_ch = mne_raw.get_data(garv_channel)[0].astype(int)

    # lookup where in the recording the event is > 0 and log_flag > 0
    bad_garv_ticks = np.where((event_ch > 0) & (garv_ch > 0))[0]

    # lower bound of annotation is time=0, upper bound is max time
    min_t = 0
    max_t = np.floor(len(event_ch) / mne_raw.info["sfreq"])

    # trim onset underruns and duration overruns, else
    onsets = [
        max(min_t, t) for t in (bad_garv_ticks / mne_raw.info["sfreq"]) + garv_start
    ]

    durations = [
        garv_duration - min(0, x) for x in max_t - (np.array(onsets) + garv_duration)
    ]

    # build the integer garv code into the description
    descriptions = [f"BAD_garv_{garv_ch[idx]}" for idx in bad_garv_ticks]

    # convert to mne format annotations
    bad_garvs = mne.Annotations(
        onset=onsets,
        duration=durations,
        description=descriptions,
        orig_time=mne_raw.annotations.orig_time,
    )
    return bad_garvs


def get_epochs_metadata(mne_raw, epochs_name):
    """retrieve mkh5 epochs table dataframe from mne.Raw.info["description"]


    Parameters
    ----------
    mne_raw : mne.Raw
       converted from a mkpy.mkh5 file that contains at least one
       named epochs table.

    epochs_name : str
       name of the epochs_table

    Returns
    -------
    pandas.DataFrame
        mne.Epochs.metadata format, one row per epoch corresponding to
        the time-locking event at time=0.

    """
    try:
        descr = json.loads(mne_raw.info["description"])
        mkh5_epochs = descr["mkh5_epoch_tables"]
        metadata = mkh5_epochs[epochs_name]
    except Exception as fail:
        msg = (
            f"{str(fail)} ... could load {epochs_name} from mne.Info['description'], "
            f"check it is in mkh5.get_epochs_table_names() before converting mkh5 "
            "to MNE raw format."
        )
        raise ValueError(msg)
    return pd.DataFrame(metadata)


def get_epochs(mne_raw, epochs_name, metadata_columns=[], **kwargs):
    """retrieve mkh5 epochs table dataframe from mne.Raw.info["description"]

    The mne.Epoch interval [tmin, tmax] matches the tmin_ms, tmax_ms
    interval mkh5.set_epochs(epochs_name, events, tmin_ms, tmax_ms).

    Parameters
    ----------
    mne_raw : mne.Raw
       The raw must have been converted from a mkpy.mkh5 file that
       contains at least one named epochs table.

    epochs_name : str
       Name of the epochs_table to get.

    metadata_columns: list of str, optional
       Specify which metadata columns to include with the epochs,
       default is all.

    **kwargs
       kwargs passed to mne.Epochs()

    Returns
    -------
        mne.Epochs

    """
    events = mne.find_events(mne_raw, epochs_name)
    metadata = get_epochs_metadata(mne_raw, epochs_name)

    # epoch interval start, stop in seconds, relative to
    # timelocking event at mne_raw_ticks
    tmins = metadata["diti_hop"] / mne_raw.info["sfreq"]
    tmaxs = (metadata["diti_len"] / mne_raw.info["sfreq"]) + tmins

    # true by construction of mkh5 epochs or die
    assert (
        len(np.unique(tmins)) == len(np.unique(tmaxs)) == 1
    ), "irregular mkh5 epoch diti_hop, diti_len"

    tmin = tmins[0]
    tmax = tmaxs[0]

    if len(metadata_columns) > 0:
        metadata = metadata[metadata_columns]

    return mne.Epochs(
        mne_raw, events, tmin=tmin, tmax=tmax, metadata=metadata, **kwargs
    )
