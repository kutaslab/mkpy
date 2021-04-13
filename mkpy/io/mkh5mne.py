"""import mkpy5 HDF5 data files to MNE Raw and Epochs, savable as .fif files"""

from pathlib import Path
import warnings
import logging
from datetime import datetime, timezone
from copy import deepcopy
import re
import json
import yaml
import numpy as np
import pandas as pd
import mkpy.mkh5 as mkh5
from mkpy import dpath  # local fork of dpath
from mkpy import __version__ as mkpy_version

import mne
from mne.io.constants import FIFF
from mne.utils.numerics import object_hash  # for comparing MNE objects


# TODO simple logging
logger = logging.getLogger("mneio_mkh5")  # all for one, one for all
logger.propoagate = False  # in case of multiple imports

__MKH5MNE_VERSION__ = mkpy_version

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
MKH5_EEG_UNIT = 1e-6  # mkh5 is calibrated to microvolts

MKH5_STIM_CHANNELS = ["raw_evcodes", "log_evcodes", "log_ccodes", "log_flags", "pygarv"]

GARV_ANNOTATION_KEYS = ["event_channel", "tmin", "tmax", "units"]

KWARGS = {
    "dblock_paths": None,  # optional, selects listed dblock_paths
    "garv_annotations": None,  # optional
    "fail_on_info": False,  # optional
    "fail_on_montage": True,  # optional
    "apparatus_yaml": None,  # optional
    "verbose": "info",  # optional
    "ignore_keys": [],  # optional
}

# these info keys can vary by mkh5 dblock, exclude from identity tests
IGNORE_INFO_KEYS = ["file_id", "meas_id", "proj_name", "subject_info"]

# for apparatus header
FIDUCIAL_KEYS = ["lpa", "rpa", "nasion"]

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
        self.args = (
            message + dbp_str + self.args[0] + ", check the .yhdr YAML\n" + bad_str,
        )


class Mkh5HeaderKeyError(Mkh5HeaderError):
    """Missing a key required for MNE import

    :meta private:
    """


class Mkh5HeaderValueError(Mkh5HeaderError):
    """value is the wrong type for MNE import

    :meta private:
    """


class Mkh5HeaderTypeError(Mkh5HeaderError):
    """illegal value for MNE import

    :meta private:
    """


# ------------------------------------------------------------
# miscellaneous exceptions
class Mkh5FileAccessError(Exception):
    """file error

    :meta private:
    """

    def __init__(self, msg):
        self.args = (msg,)


class Mkh5InfoUpdateError(Exception):
    """report failed info update attempts

    :meta private:
    """

    def __init__(self, mne_info_key, bad_value):
        msg = "failed to set mne info[{mne_info_key}] = {bad_value}"
        self.args = (msg,)


class Mkh5DblockPathError(Exception):
    """tried to access a non-existent datablock

    h5py also throws an error but the message is generic
    "object not found" without specifying what object.

    :meta private:
    """

    def __init__(self, fail_msg, mkh5_f, dbp):
        msg = f"{fail_msg}: {mkh5_f} {dbp}"
        self.args = (msg,)


# ------------------------------------------------------------
# mkh5 epochs  table errors
class EpochsMkh5EpochsNameError(ValueError):
    """tried to access a non-existent epochs table

    :meta private:
    """

    def __init__(self, mkh5_f, epochs_name):
        msg = (
            f"in {mkh5_f} cannot locate epochs table {epochs_name}, "
            "check mkh5.get_epoch_table_names()"
        )
        self.args = (msg,)


class EpochsMkh5ExcludedDataBlockError(ValueError):
    """tried to access a non-existent mkh5 data block

    :meta private:
    """

    def __init__(self, mkh5_f, epochs_name, missing_dblocks):
        msg = (
            (
                f"epochs table {epochs_name} requires data the following "
                f"{mkh5_f} dblock_paths, include them them to list of selected"
                f"dblock_paths=[...] or set dblock_paths=None to select all: "
            )
            + "["
            + ", ".join(dbp for dbp in missing_dblocks)
            + "]"
        )
        self.args = (msg,)


class EpochsMkh5ColumnNameError(ValueError):
    """non-existent epochs_id or time column in the epochs table

    :meta private:
    """

    def __init__(self, mkh5_f, epochs_name, col):
        msg = (
            f"{mkh5_f} epochs table {epochs_name} column error {col}, check"
            f" {epochs_name}.columns"
        )
        self.args = (msg,)


class EpochsMkh5NonZeroTimestamps(ValueError):
    """values in mkh5 timestamp column vary or differ from the timelock=value

    :meta private:
    """

    def __init__(self, mkh5_f, epochs_name, col):
        msg = (
            f"{mkh5_f} epochs table {epochs_name} time column {col} has"
            "non-zero timestamps. MNE epochs, (tmin, tmax) are defined relative"
            "to the timelock event at time=0. Inspect the epochs table in"
            f" {mkh5_f} with mkh5.mkh5.get_epochs_table({epochs_name})"
            " to locate the discrepant timestamps. If the mkh5 event table"
            " is overgenerating match_time events with non-zero time-stamps,"
            f" prune the rows with non-zero timesamps in {col}, and set"
            "the epochs with the new event table mkh5.mkh5.set_epochs(event_table)."
        )
        self.args = (msg,)


# ------------------------------------------------------------
# Apparatus YAML file
class ApparatusYamlFileError(Exception):
    """yaml file didn't open for any reason

    :meta private:
    """

    def __init__(self, msg):
        self.args = (f"{msg} check file name, path, and permissions",)


# ------------------------------------------------------------
# MNE structure exceptions
class Mkh5DblockInfoMismatch(Exception):
    """raised if MNE info structures differ, e.g., across mkh5 dblocks

    :meta private:
    """

    def __init__(self, msg_1, msg_2):
        self.args = (msg_1 + "\n" + msg_2,)


class Mkh5DblockMontageMismatch(Exception):
    """raised if MNE montage structures differ, e.g., across mkh5 dblocks

    :meta private:
    """

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


def _check_mkh5_event_channel(mne_raw, channel):
    """check channel is stim or misc with integer-like events"""

    event_channel_types = dict(stim=True, misc=True)
    chan_idxs = mne.pick_types(mne_raw.info, **event_channel_types)
    error_msg = None
    try:
        if not channel in np.array(mne_raw.info["ch_names"])[chan_idxs]:
            error_msg = (
                f"{channel} must be type: {', '.join(event_channel_types.keys())}"
            )

        if not all(
            mne_raw[channel][0].squeeze() == mne_raw[channel][0].squeeze().astype(int)
        ):
            error_msg = f"{channel} data does look like integer event codes"
        if error_msg:
            raise ValueError(error_msg)
    except Exception as exc:
        raise ValueError from exc


def _check_api_params(_class, mkh5_f, **kwargs):
    """screen mkh5_f, dblock paths and epoch names prior to processing

    Parameters
    ----------
    _class : Mkh5Raw

    mkh5_f : str
        path to mkh5 file

    **kwargs
        see module KEYWARGS

    """
    # mne and mkh5
    _check_package_versions()

    # API feeds parameters to the classes, user actions cannot
    # make the assertions fail
    # assert _class in [Mkh5Raw, EpochsMkh5], \
    assert _class is Mkh5Raw, "_check_api_params _class must be Mkh5Raw"

    # set the module kwargs for the input class Mkh5Raw # or EpochsMkh5
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
    if not isinstance(mkh5_f, (str, Path)):
        msg = "mkh5 must be a path to an mkpy.mkh5 HDF5 file"
        raise ValueError(msg)

    # ------------------------------------------------------------
    # verbose
    verbose = kwargs["verbose"]
    if verbose not in VERBOSE_LEVELS:
        msg = f"verbose={verbose} level must be: {' '.join(VERBOSE_LEVELS)}"
        raise ValueError(msg)

    # ------------------------------------------------------------
    # arg: mkh5 file and dblock check
    if not Path(mkh5_f).exists():
        msg = f"{mkh5_f} not found, check file path and name"
        raise Mkh5FileAccessError(msg)

    # this must work
    h5_data = mkh5.mkh5(mkh5_f)

    # e.g., dblock_paths=["group/dblock_0", "group/dblock_1", ...]  or all
    assert kwargs["dblock_paths"] is not None, "set dblock_paths=[...], else very slow"
    kw_dblock_paths = kwargs["dblock_paths"]

    if not (
        isinstance(kw_dblock_paths, list)
        and all([isinstance(dbp, str) for dbp in kw_dblock_paths])
    ):
        msg = f"dblock_paths={kw_dblock_paths} must be a list of strings"
        raise TypeError(msg)

    h5_dblock_paths = h5_data.dblock_paths
    for kw_dbp in kw_dblock_paths:
        if kw_dbp[0] == r"/":
            raise ValueError(
                f"There is no root / in mkh5 datablock paths, try {kw_dbp[1:]}"
            )
        if kw_dbp not in h5_dblock_paths:
            raise IOError(f"{kw_dbp} not found in {mkh5_f}")

    # ------------------------------------------------------------
    # garv annotations
    if kwargs["garv_annotations"]:
        garv_anns = kwargs["garv_annotations"]

        if not isinstance(garv_anns, dict):
            raise TypeError("garv_annotations must be a dictionary")

        if not set(garv_anns.keys()) == set(GARV_ANNOTATION_KEYS):
            raise KeyError(f"garv_annotations keys must be {GARV_ANNOTATION_KEYS}")

        if garv_anns["units"] not in ["ms", "s"]:
            msg = f"garv annotation units must be 'ms' or 's"
            raise ValueError(msg)

        t_scale = 1000.0 if garv_anns["units"] == "ms" else 1.0

        # let python raise TypeError for non-numerical values
        garv_start = garv_anns["tmin"] / t_scale
        garv_stop = garv_anns["tmax"] / t_scale

        if not garv_start < garv_stop:
            msg = f"garv interval must have the start < stop"
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

    if kwargs["ignore_keys"]:
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

    # full set of checked kwargs for _class Mkh5Raw or EpochsMkh5
    return kwargs


def _is_equal_mne_info(info_a, info_b, exclude=None, verbose=False):
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
    if exclude is None:
        exclude = []

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


def _check_info_montage_across_dblocks(mkh5_f, ignore_keys=None, **kwargs):
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
    ignore_keys : list of str or None (default)
        differences between the values of these info keys are ignored even
        when fail_on_info=True, see IGNORE_INFO_KEYS. Default None
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

    if ignore_keys is None:
        ignore_keys = []

    # clunky but clear ...
    dblock_paths = kwargs["dblock_paths"]
    apparatus_yaml = kwargs["apparatus_yaml"]
    fail_on_info = kwargs["fail_on_info"]
    fail_on_montage = kwargs["fail_on_montage"]
    verbose = kwargs["verbose"]

    if fail_on_info:
        verbose = "info"  # fail informatively

    h5data = mkh5.mkh5(mkh5_f)

    # enforce explicit dblock_paths kwarg
    assert dblock_paths is not None, "set dblock_paths kwarg, else too slow"

    # check pairwise against first
    dbp_i = dblock_paths[0]
    hdr_i, _ = h5data.get_dblock(dbp_i)
    info_i, montage_i = _hdr_dblock_to_info_montage(
        hdr_i, apparatus_yaml=apparatus_yaml
    )

    for dbp_j in dblock_paths[1:]:

        print(f"checking info, montage {dbp_j}")

        hdr_j, _ = h5data.get_dblock(dbp_j)
        info_j, montage_j = _hdr_dblock_to_info_montage(
            hdr_j, apparatus_yaml=apparatus_yaml
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


def _check_mkh5_mne_epochs_table(mne_raw, epochs_name, epochs_table):
    """check mkh5 event_table event code data agrees with mne.Raw channel data"""

    error_msg = None
    if epochs_name not in mne_raw.info.ch_names:
        error_msg = (
            "mne.Raw event channel {epochs_name} not found, make sure"
            " it is an epochs table name in the mkh5 file"
        )

    if epochs_name not in [
        mne_raw.info.ch_names[i] for i in mne.pick_types(mne_raw.info, stim=True)
    ]:
        error_msg = (
            "{epochs_name} is not an mne stim channel type, make sure this"
            " mne.Raw was converted from mkh5 with mkh5mne.read_raw()"
        )

    # mkpy epochs allow one-many event tags, MNE metadata
    # must be 1-1 with mne.Raw["event_channel} events: [sample, 0, event]
    duplicates = epochs_table[epochs_table.duplicated("mne_raw_tick")]
    if len(duplicates):
        error_msg = (
            f"mkh5 epochs {epochs_name} cannot be used as"
            f" mne.Epoch.metadata, duplicate mne_raw_tick: {duplicates}"
        )

    if error_msg:
        raise ValueError(error_msg)

    # check channel data at mne tick agrees with epoch table
    check_cols = set(mne_raw.info.ch_names).intersection(set(epochs_table.columns))
    for col in check_cols:
        mne_col = mne_raw.get_data(col).squeeze()[epochs_table["mne_raw_tick"]]
        errors = epochs_table.where(epochs_table[col] != mne_col).dropna()
        if len(errors):
            error_msg = (
                f"mkh5 epochs table {epochs_name}['{col}'] does not match"
                " mne.Raw data at these mne_raw_tick:\n"
            )
            error_msg += "\n".join(
                [
                    (
                        f"epochs_table[{col}]: {error[col]}"
                        f" mne.Raw[{col, int(error['mne_raw_tick'])}]: "
                        f"{mne_raw.get_data(col).squeeze()[int(error['mne_raw_tick'])]}"
                    )
                    for _, error in errors.iterrows()
                ]
            )
            raise ValueError(error_msg)

    # non-zero events on the named "event" channel must be 1-1
    # with tagged events from mkh5 in the same-named epochs table
    mne_raw_epoch_events = mne_raw[epochs_name][0].squeeze()[
        np.where(mne_raw[epochs_name][0].squeeze() != 0)
    ]

    mkh5_epoch_events = epochs_table["log_evcodes"]
    n_raw_events = len(mne_raw_epoch_events)
    n_epoch_table_events = len(mkh5_epoch_events)
    if not all(mne_raw_epoch_events == mkh5_epoch_events):
        error_msg = (
            f"The sequence of non-zero log_evcodes on channel"
            f" mne.Raw[{epochs_name}] (n={n_raw_events})"
            f" must match the sequence of log_evcodes in the"
            f" mkpy epochs table {epochs_name} (n={n_epoch_table_events})."
        )
        raise ValueError(error_msg)


class Mkh5Raw(mne.io.BaseRaw):
    """Raw MNE compatible object from mkpy.mkh5 HDF5 data file

    This class is not meant to be instantiated directly, use
    :py:func:`mkh5mne.from_mkh5` and see those docs.

    :meta private:
    """

    def __init__(
        self,
        mkh5_f,
        garv_annotations=None,
        dblock_paths=None,
        fail_on_info=False,
        fail_on_montage=True,
        apparatus_yaml=None,
        verbose="info",
        ignore_keys=None,
    ):

        if ignore_keys is None:
            ignore_keys = IGNORE_INFO_KEYS

        if dblock_paths is None:
            print(mkh5_f)
            print("looking up data block paths, larger files take longer ...")
            dblock_paths = mkh5.mkh5(mkh5_f).dblock_paths
        print("ok")

        _kwargs = _check_api_params(
            Mkh5Raw,
            mkh5_f,
            dblock_paths=dblock_paths,
            garv_annotations=garv_annotations,
            fail_on_info=fail_on_info,
            fail_on_montage=fail_on_montage,
            apparatus_yaml=apparatus_yaml,
            verbose=verbose,
            ignore_keys=ignore_keys,
        )
        _check_info_montage_across_dblocks(mkh5_f, **_kwargs)

        # ------------------------------------------------------------
        # mkh5 block are converted to self contained mne.RawArray and MNE
        # does the bookeeping for concatenting the RawArrays. Not future
        # proof but perhaps more future resistant.
        raw_dblocks = []
        mne_ditis = dict()
        raw_samp_n = 0  # track accumulated samples across data blocks
        for dbpi, dbp in enumerate(dblock_paths):

            # raw_dblock is an instance of mne.Raw, db_epts is a dic with keys in
            # epoch_names and vals = the mkh5 epochs table dataframe row sliced
            # for this data block path.
            raw_dblock, db_epts = _dblock_to_raw(
                mkh5_f,
                dbp,
                garv_annotations=garv_annotations,
                apparatus_yaml=apparatus_yaml,
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
                diti["mne_raw_tick"] = raw_samp_n + diti["dblock_ticks"]
                if key not in mne_ditis.keys():
                    # start a new table w/ mne raw ticks counting from 0
                    mne_ditis[key] = diti
                else:
                    # continue an existing table
                    assert all(mne_ditis[key].columns == diti.columns)
                    mne_ditis[key] = mne_ditis[key].append(diti)
            raw_samp_n += len(raw_dblock)

        # assemble RawArrays
        mne_raw = mne.io.concatenate_raws(raw_dblocks, preload=True)
        info = deepcopy(mne_raw.info)

        # convert epochs table dataframes to dicts for JSONification
        for epochs_name, epochs_table in mne_ditis.items():

            _check_mkh5_mne_epochs_table(mne_raw, epochs_name, epochs_table)
            mne_ditis[epochs_name] = epochs_table.to_dict()

        # look up mkh5 file format version
        mkh5_f_version = []
        for dbp in dblock_paths:
            hdr = mkh5.mkh5(mkh5_f).get_dblock(dbp, dblock=False)
            mkh5_f_version.append(hdr["mkh5_version"])

        # should be OK unless tampered with
        assert (
            len(set(mkh5_f_version)) == 1
        ), "mkh5 file versions cannot vary across dblocks"

        # epochs_table tagged event info really belongs attached to
        # the raw, e.g., raw._ditis map of ditis but mne.Raw doesn't
        # allow it.

        # info["description"] = json.dumps({"mkh5_epoch_tables": mne_ditis})
        info["description"] = json.dumps(
            {
                "mkh5_epoch_tables": mne_ditis,
                "mkh5_file_version": mkh5_f_version[0],
                "mkh5mne_version": __MKH5MNE_VERSION__,
            }
        )

        # event and eeg datastreams numpy array
        data = mne_raw.get_data()
        super().__init__(
            info=info,
            preload=data,
            filenames=[str(mkh5_f)],
            # orig_format='single',
        )

        # collect boundaries, log_evcodes, and optional garv intervals
        # marked by concatenate_raw
        self.set_annotations(mne_raw.annotations)

        # or average?
        self.set_eeg_reference(
            ref_channels=[], projection=False, ch_type="eeg"  # "average"
        )

    def _read_segment_file(self):
        """we know how to save as fif, hand off reading to MNE"""
        msg = (
            "_read_segment_file() ... save Mkh5Raw as a .fif and "
            "  read with mne.io.Raw()"
        )
        raise NotImplementedError(msg)


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
            msg = "no apparatus document"
        if len(apparatus_hdrs) > 1:
            msg = "multiple apparatus documents"

        if msg:
            msg += (
                f" in {apparatus_yaml_f}, there must be exactly one "
                "YAML doc with name: apparatus"
            )
            raise Mkh5HeaderValueError(msg)

    return yaml_docs[0]


# ------------------------------------------------------------
# .yhdr header functions used by Mkh5Raw and EpochsMkh5
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

       The header must have
         h5_dataset: <str>
         samplerate: <int|float>
         and apparatus: <map>

       The apparatus must have these maps:
          common_ref: str
          space: map
          fiducials: map
          streams: map
          sensors: map
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
        msg = "header is missing required key: h5_dataset"
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
        msg = "header has no samplerate key"
        raise Mkh5HeaderKeyError(msg, dblock_path)

    if not isinstance(hdr["samplerate"], (int, float)):
        msg = "header samplerate must be numeric (integer or float)"
        sub_hdr = dpath.search("hdr", "samplerate")
        raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)

    # sfreq = hdr["samplerate"]

    # ------------------------------------------------------------
    # these key: vals are user specified YAML, anything can happen.

    # there must be an apparatus map
    if "apparatus" not in hdr.keys():
        msg = "apparatus map not found"
        raise Mkh5HeaderKeyError(msg, dblock_path)

    # ------------------------------------------------------------
    # apparatus must have stream, sensor, fiducial, common_ref  maps
    for key in ["streams", "sensors", "fiducials", "common_ref", "space"]:
        if key not in hdr["apparatus"]:
            msg = f"apparatus {key} map not found"
            raise Mkh5HeaderKeyError(msg, dblock_path)

    # ------------------------------------------------------------
    space = {
        "coordinates": "cartesian",
        "orientation": "ras",
        "distance_unit": ["m", "cm", "mm"],
    }
    hdr_space = dpath.util.values(hdr, "apparatus/space")[0]
    for key in space.keys():
        if key not in hdr_space.keys():
            msg = f"apparatus space map must include {key}: {space[key]}"
            raise Mkh5HeaderKeyError(msg, dblock_path)

        # check units for scaling to MNE meters:
        if key == "distance_unit":
            if hdr_space[key] not in space[key]:
                msg = f"apparatus space map {key} must be one of these: {space[key]}"
                raise Mkh5HeaderValueError(msg, dblock_path, hdr_space)

        elif not hdr_space[key] == space[key]:
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
    hdr_mne_stream_key_vals = {
        "mne_type": MNE_STREAM_TYPES,  # eeg, eog, stim, misc, ...
        "pos": hdr_sensors,  # these provide the 3D coordinates
        "neg": hdr_sensors,  # these provide the 3D coordinates
    }

    for stream, val in hdr["apparatus"]["streams"].items():

        sub_hdr = dpath.util.search(hdr, f"apparatus/streams/{stream}")

        # check the mne_type, pos, neg keys
        for key in hdr_mne_stream_key_vals.keys():
            if key not in val.keys():
                msg = f"apparatus stream {key} not found"
                raise Mkh5HeaderKeyError(msg, dblock_path, sub_hdr)

        # check the values
        for key, vals in hdr_mne_stream_key_vals.items():
            if not val[key] in vals:
                msg = (
                    f"apparatus stream {stream} {key} value must"
                    f"be one of these: <{'|'.join(vals)}>"
                )
                raise Mkh5HeaderValueError(msg, dblock_path, sub_hdr)

    # ------------------------------------------------------------
    # fiducial keys are lpa, rpa, nasion
    for fid_key in FIDUCIAL_KEYS:
        if fid_key not in hdr["apparatus"]["fiducials"].keys():
            sub_hdr = dpath.util.search(hdr, "apparatus/fiducials")
            msg = (
                "apparatus fiducials (lpa, rpa, nasion) location "
                f"{fid_key} not found"
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


def _parse_hdr_for_mne(hdr, apparatus_yaml=None):
    """convert mkh5 header info for use in MNE dig montage and info

    The user-specified hdr["apparatus"]["streams]["mne_type"] values from the
    the YAML .yhdr are used, all the rest of the data block columns are
    assigned MNE type "misc".

    All 3D cartesian soordinates are scaled to MNE-native meters based
    on header units: m, cm, mm.

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

    # since eeg data streams don't have a "location" use
    # coordinates from the positive pinout electrode
    apparatus_streams = apparatus_streams.join(apparatus_sensors, how="left", on="pos")

    # collect the fiducials
    apparatus_fiducials = pd.DataFrame.from_dict(
        hdr["apparatus"]["fiducials"], orient="index"
    ).rename_axis(index="fiducial")

    # collect the coordinate space
    space = {"space": hdr["apparatus"]["space"].copy()}

    # m, cm, mm units are guarded in _validate_hdr_for_mne
    yhdr_units_scaled_by = None
    unit = hdr["apparatus"]["space"]["distance_unit"]
    if unit == "m":
        yhdr_units_scaled_by = 1.0
    if unit == "cm":
        yhdr_units_scaled_by = 0.01
    if unit == "mm":
        yhdr_units_scaled_by = 0.001
    assert yhdr_units_scaled_by is not None, "bad distance unit in apparatus space map"
    space["space"]["yhdr_units_scaled_by"] = yhdr_units_scaled_by

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

    # update known mkh5 dblock streams to mne_types
    hdr_streams.loc[MKH5_STIM_CHANNELS, "mne_type"] = "stim"
    hdr_streams.loc[pd.isna(hdr_streams["mne_type"]), "mne_type"] = "misc"

    # 3D sensor coordinate dicts -> in MNE key: [R, A, S, ... ] in MNE-native meters
    # fiducial landmarks in MNE label: [x, y, z] in MNE-native meters
    fiducials = apparatus_fiducials.apply(
        lambda row: row.to_numpy(dtype=float) * yhdr_units_scaled_by, axis=1
    ).to_dict()

    # for mne.channels.make_dig_montage
    dig_ch_pos = apparatus_streams.apply(
        lambda row: row[["x", "y", "z"]].to_numpy(dtype=float) * yhdr_units_scaled_by,
        axis=1,
    ).to_dict()

    # for info["chs"][i]["loc"] = array, shape(12,)
    # first 3 are positive sensor, next 3 are reference (negative)
    # but MNE DigMontage chokes on mixed common ref (A1) and biploar
    # so skip the reference location.

    # 3D coordinates are MNE-native meters
    info_ch_locs = {}
    for chan, _ in apparatus_streams.iterrows():
        # e.g., A1 for common reference, lhz for bipolar HEOG.
        pos = apparatus_streams.loc[chan, "pos"]
        # neg = apparatus_streams.loc[ch, "neg"]   # not used
        pos_locs = apparatus_sensors.loc[pos, :]
        info_ch_locs[chan] = (
            np.hstack(
                # [pos_locs, ref_locs, np.zeros((6, ))] # the truth
                [pos_locs, np.zeros((9,))]  # what works w/ MNE
            )
            * yhdr_units_scaled_by
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

    global MKH5_EEG_UNIT is the critical EEG scaling factor, so that RawArray
    data * MKH5_EEG_UNIT set in dblock conversion from native mkh5 uV to the
    FIFF.FIFF_UNIT_V channel scale set here in the MNE channel info
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
    for ch_info in info["chs"]:
        ch_name = ch_info["ch_name"]
        is_eeg = ch_info["kind"] == FIFF.FIFFV_EEG_CH
        is_eog = ch_info["kind"] == FIFF.FIFFV_EOG_CH
        if is_eeg or is_eog:

            # update ch locs from parsed hdr["apparatus"]["sensor"]
            ch_info["loc"] = hdr_mne["info_ch_locs"][ch_name]

            # CRITICAL, must be true when MKH5_EEG_UNITS = 1e-6
            assert ch_info["unit"] == FIFF.FIFF_UNIT_V

            # mkh5 data blocks may or may not be calibrated
            if not (
                "calibrated" in hdr["streams"][ch_name].keys()
                and hdr["streams"][ch_name]["calibrated"]
            ):
                msg = (
                    f"mkh5 data {hdr['h5_dataset']} {ch_name} is not calibrate"
                    f"setting default mne.info[{ch_name}]['cal'] = 1.0"
                )
                warnings.warn(msg)
                ch_info["cal"] = 1.0
            else:
                # log A/D cal factor the MNE way
                ch_info["cal"] = 1.0 / hdr["streams"][ch_name]["cals"]["scale_by"]

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
def _dblock_to_raw(
    mkh5_f, dblock_path, garv_annotations=None, apparatus_yaml=None,
):
    """convert one mkh5 datablock+header into one mne.RawArray

    Ingest one mkh5 format data block and return an mne.RawArray
    populated with enough data and channel information to use mne.viz
    and the mne.Epochs, mne.Evoked EEG pipeline.

    Parameters
    ----------
    dblock_path : str
       HDF5 slash path to an mkh5 data block which an h5py.Dataset
    garv_annotations: None or dict
       event_channel: str, channel name with events to annotate
       start, stop: float relative to time lock event
       unit: "ms" or "s"
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
    h5data = mkh5.mkh5(mkh5_f)
    try:
        assert dblock_path in h5data.dblock_paths, "please report this bug"
        hdr, dblock = h5data.get_dblock(dblock_path)
    except Exception as fail:
        raise Mkh5DblockPathError(str(fail), mkh5_f, dblock_path)

    info, montage = _hdr_dblock_to_info_montage(hdr, apparatus_yaml=apparatus_yaml)

    # mne wants homogenous n_chans x nsamps, so stim, misc ints coerced
    # to float ... sigh.
    mne_data = np.ndarray(shape=(len(dblock.dtype.names), len(dblock)), dtype="f8")

    # slice out and scale mkh5 native uV to mne FIFFV_UNIT_V
    for jdx, stream in enumerate(dblock.dtype.names):
        # true by construction unless tampered with
        assert info["ch_names"][jdx] == stream
        assert hdr["streams"][stream]["jdx"] == jdx

        # CRITICAL ... mkh5 EEG are native uV, MNE are V
        if "dig_chan" in hdr["streams"][stream]["source"]:
            mne_data[jdx] = dblock[stream] * MKH5_EEG_UNIT
        else:
            mne_data[jdx] = dblock[stream] * 1.0

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
            epochs_table = h5data.get_epochs_table(etn)
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

            # true by construction of mkh5 except MNE is dtype float
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
    if garv_annotations:
        print(f"annotating garv artifacts {garv_annotations}")
        bad_garvs = get_garv_bads(raw_dblock, **garv_annotations)
        raw_dblock.set_annotations(raw_dblock.annotations + bad_garvs)

    return raw_dblock, epochs_table_descr


def _hdr_dblock_to_info_montage(hdr, apparatus_yaml=None):
    """populate MNE structures with mkh5 data"""

    hdr_mne = _parse_hdr_for_mne(hdr, apparatus_yaml)

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
    """this checks epochs in the mkh5"""

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
def find_mkh5_events(mne_raw, channel_name):
    """Replacement for mne.find_events for mkh5 integer event code channels

    Finds single-sample positive and negative integer event codes and returns
    them without modification unlike `mne.find_events()` which switches
    the sign of negative event codes.

    Parameters
    ----------
    mne_raw : Mkh5Raw or mne.io.Raw object
        data with the stim channel to search

    channel_name : str
       name of the channel to search for non-zero codes

    Returns
    -------
    event_array : np.array
       Three column MNE format where event_array[idx, :] = [sample, 0, code]

    Raises
    ------
    ValueError
       If `channel_name` does not exist.
    TypeError
        If `channel_name` is not an MNE 'stim' type channel.

    Example
    -------
    >>> mne_raw = mkh5mne("sub01.h5")
    >>> mne_events = mkh5mne.find_mkh5_events(mne_raw, "p3")


    """

    if channel_name not in np.array(mne_raw.info["ch_names"]):
        raise ValueError(f"channel {channel_name} not found")

    stim_chan_idxs = mne.pick_types(mne_raw.info, stim=True)
    if channel_name not in np.array(mne_raw.info["ch_names"])[stim_chan_idxs]:
        msg = f"{channel_name} is not a stim or misc channel according to mne.Info"
        raise TypeError(msg)

    # _name is MNE stim channel added by from_mkh5()
    event_stream = mne_raw[channel_name][0].squeeze().astype(int)
    idxs = np.where(event_stream != 0)[0]
    codes = event_stream[idxs]

    return np.array([idxs, np.zeros(len(idxs)), codes], dtype=int).T


def read_raw_mkh5(
    mkh5_file,
    garv_annotations=None,
    dblock_paths=None,
    apparatus_yaml=None,
    fail_on_info=False,
    fail_on_montage=True,
    verbose="info",
):
    """Read an mkh5 data file into MNE raw format

    .. deprecated:: 
    Use :func:`from_mkh5`

    """
    warnings.warn(
        "mkh5mne.read_raw_mkh5() is deprecated and will be removed in a future release,"
        " use mkh5mn3.from_mkh5() instead"
    )

    return from_mkh5(
        mkh5_file,
        garv_annotations=garv_annotations,
        dblock_paths=dblock_paths,
        fail_on_info=fail_on_info,
        fail_on_montage=fail_on_montage,
        apparatus_yaml=apparatus_yaml,
        verbose=verbose,
    )


def from_mkh5(
    mkh5_f,
    garv_annotations=None,
    dblock_paths=None,
    apparatus_yaml=None,
    fail_on_info=False,
    fail_on_montage=True,
    verbose="info",
):

    """Read an mkh5 data file into MNE raw format

    The mkh5 EEG data, events are converted to mne.BaseRaw for use
    with native MNE methods. The mkh5 timelock events and tags in the
    epochs tables are added to the raw data and mne.Info for use as
    MNE events and metadata with mne.Epochs.


    Parameters
    ----------
    mkh5_f: str
        File path to a mkpy.mkh5 HDF5 file

    garv_annotations: None | dict, optional
        event_channel: (str)  # channel name with events to annotate
        tmin, tmax: (float)  # relative to time lock event
        units: "ms" or "s". Defaults to None.

    dblock_paths : None | list of mkh5 datablock paths, optional
        The listed datablock paths will be concatenated in order into the 
        mne.Raw. Defaults to None, in which case all the data blocks in mkh5 file
        are concatenated in the order returned by :py:meth:`.mkh5.dblock_paths`.

    apparatus_yaml : None | str, optional
        If a path to a well-formed mkh5 apparatus map YAML file, it
        is used instead of the map in the mkh5 dblock header, if any.
        Defaults to None.
        
    fail_on_info : bool, optional
        If True, this enforces strict mne.Info identity across the
        mkh5 data blocks being concatenated. If False (default), some
        deviations between mne.Info for the mkh5 data blocks are
        allowed, e.g., for pooling multiple subject files into an
        experiment or separate cals for a single subject. Defaults to False.

    fail on montage : bool, optional
       If True, the mne.Montage created from the mkh5 header
       data streams and channel locations must be the same for all the
       data blocks. If False, mkh5mne allows the MNE montage to vary across mkh5 data
       blocks and leaves you to deal with whatever :py:meth:`mne.concatenate_raws` does
       in this case. Defaults to True

    verbose : NotImplemented


    Returns
    -------
    Mkh5Raw
        subclassed from mne.BaseRaw for use as native MNE.

    Raises
    ------
    Exceptions
        if data block paths or apparatus map information is
        misspecified or the info and montage test flags are set and fail.


    Notes
    -----

    EEG and events.
        The mkh5 data block columns are converted to mne
        channels and concatenated into a single mne Raw in the order
        given by `dblock_paths`. The default is to convert the entire
        mkh5 file in `mkh5.dblock_paths` order.

    Epochs.
        The mkh5 epochs table time locking events are indexed to the
        mne.Raw data samples and the epoch tables stored as a JSON
        string in the `description` field of :py:class"`mne.Info`. The
        named mkh5 format epochs table is recovered by converting the
        JSON to a pandas.DataFrame which is well-formed
        mne.Epochs.metadata for the events on the `epochs_name` stim
        channel.


    Examples
    -------
    >>> mne_raw = mkh5mne("sub01.h5")

    >>> mne_raw = mkh5mne.from_mkh5(
            "sub01.h5",
            garv_annotations=dict(
                event_channel="log_evcodes", tmin=-500, tmax=500, units="ms"
            )
       )

    >>> mne_raw = mkh5mne(
            "sub01.h5",
            dblock_paths=["sub01/dblock_0", "sub01/dblock_1"]  # first two dblocks only
        )

    """

    return Mkh5Raw(
        mkh5_f,
        garv_annotations=garv_annotations,
        dblock_paths=dblock_paths,
        apparatus_yaml=apparatus_yaml,
        fail_on_info=fail_on_info,
        fail_on_montage=fail_on_montage,
        verbose=verbose,
    )


def get_garv_bads(
    mne_raw,
    event_channel=None,
    tmin=None,
    tmax=None,
    units=None,
    garv_channel="log_flags",
):
    """create mne BAD_garv annotations spanning events on a stim event channel

    This time locks the annotation to non-zero events on event_channel that
    have a non-zero codes on the log_flags column, e.g., as given by
    as given by running avg -x -a subNN.arf to set log_flags in
    subNN.log.

    The annotations may be attached to an mne.Raw for triggering artifact
    exclusion during epoching.

    Parameters
    ----------
    mne_raw : mne.Raw
        mne.Raw data object converted from mkh5
    event_channel : str
        name of the mne channel with events to annotate with BAD_garv
    tmin, tmax: float
        interval to annotate, relative to time lock event, e.g., -500, 1000
    unit: {"ms", "s"}
        for the interval units as milliseconds or seconds
    garv_channel : str, optional
         name of the channel to check for non-zero codes at time-lock
         events. The default="log_flags" is where avg -x puts garv rejects,
         other routines may use other channels.

    Returns
    -------
    mne.Annotations
        formatted as ``BAD_garv_N`` where N is the non-zero log_flag value

    Examples
    --------
    >>>  mkh5mn3.get_garv_bads(
             mne_raw,
             event_channel="p3_events",
             tmin=-500,
             tmax=1000,
             units="ms"
         )

    """
    # modicum of validation
    msg = None
    try:
        _check_mkh5_event_channel(mne_raw, event_channel)
        if not tmin < tmax:
            raise ValueError("bad garv interval, ")
        if units == "s":
            pass
        elif units == "ms":
            tmin /= 1000.0
            tmax /= 1000.0
        else:
            raise ValueError("bad units, ")
    except Exception as fail:
        msg = (
            "garv bads event_channel must be be a stim channel in the raw,"
            " garv interval must be tmin < tmax with units 'ms' or 's'"
        )
        raise ValueError(msg) from fail

    garv_duration = tmax - tmin

    # epoch event channel column
    event_ch = mne_raw.get_data(event_channel)[0].astype(int)

    # artifact channel column
    garv_ch = mne_raw.get_data(garv_channel)[0].astype(int)

    # lookup where in the recording the event artifact flag != 0 and log_flag != 0
    bad_garv_ticks = np.where((event_ch != 0) & (garv_ch != 0))[0]

    # lower bound of annotation is time=0, upper bound is max time
    min_t = 0
    max_t = np.floor(len(event_ch) / mne_raw.info["sfreq"])

    # trim onset underruns and duration overruns, else
    onsets = [max(min_t, t) for t in (bad_garv_ticks / mne_raw.info["sfreq"]) + tmin]

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

    # lots can go wrong, fail if anything does
    try:
        descr = json.loads(mne_raw.info["description"])
        mkh5_epochs = descr["mkh5_epoch_tables"]
        metadata = mkh5_epochs[epochs_name]
    except Exception as fail:
        error_msg = (
            f"{str(fail)} ... could not load {epochs_name} from "
            " mne.Info['description'], check it is in mkh5.get_epochs_table_names()"
            " before converting mkh5 to MNE."
        )
        raise ValueError(error_msg)

    return pd.DataFrame(metadata)


def get_epochs(mne_raw, epochs_name, metadata_columns="all", **kwargs):
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

    metadata_columns: "all" or list of str, optional
       Specify which metadata columns to include with the epochs,
       default is all.

    **kwargs
       kwargs passed to mne.Epochs()

    Returns
    -------
        mne.Epochs

    """

    metadata = get_epochs_metadata(mne_raw, epochs_name)
    _check_mkh5_mne_epochs_table(mne_raw, epochs_name, metadata)

    error_msg = None
    if metadata_columns != "all":
        if not isinstance(metadata_columns, list):
            error_msg = "metadata_columns must be a list of metadata column names"
        for col in metadata_columns:
            if not (isinstance(col, str) and col in metadata.columns):
                error_msg = f"{col} is not a metadata data column"
    if error_msg:
        raise ValueError(error_msg)

    # epoch interval start, stop in seconds, relative to
    # timelocking event at mne_raw_tick
    tmins = metadata["diti_hop"] / mne_raw.info["sfreq"]
    tmaxs = (metadata["diti_len"] / mne_raw.info["sfreq"]) + tmins

    # true by construction of mkh5 epochs or die
    assert (
        len(np.unique(tmins)) == len(np.unique(tmaxs)) == 1
    ), "irregular mkh5 epoch diti_hop, diti_len"

    tmin = tmins[0]
    tmax = tmaxs[0]

    if metadata_columns != "all":
        metadata = metadata[metadata_columns]

    # native MNE event lookup
    events = find_mkh5_events(mne_raw, epochs_name)
    return mne.Epochs(
        mne_raw, events, tmin=tmin, tmax=tmax, metadata=metadata, **kwargs
    )
