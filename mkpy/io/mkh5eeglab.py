# Authors: Thomas P. Urbach
#
# License: BSD (3-clause)
#
# _write_set based on https://github.com/cbrnr/mnelab/blob/main/mnelab/io/writers.py
# Authors: Clemens Brunner <clemens.brunner@gmail.com>
# License: BSD (3-clause)

import re
import json
import numpy as np

# from numpy.core.records import fromarrays
import pandas as pd
from scipy.io import savemat
from mkpy.io import mkh5mne


def mkh5raw_to_set(mkh5raw, fname, epochs_name=None):
    """Export mkh5raw EEG, channel, and event data to an EEGLAB .set file.

    The EEGLAB .set file is populated with EEG and event data
    channels, channel names and locations, event codes and tags and
    all the annotations in `mkh5raw` including garv annotations if
    previously set.

    Parameters
    ==========
    mkh5raw : mkh5mne.RawMkh5 instance
       As returned by mkh5mne.from_mkh5(), see
       :py:func:`.mkh5mne.from_mkhg` docs for usage.

    fname : str
       Path to the EEGLAB set file to create.

    epochs_name : str, optional
       Also export the codemap event tags in the named epochs table. Defaults to None.

    """
    data = mkh5raw.get_data()  # already converted * 1e6  # convert to microvolts
    fs = mkh5raw.info["sfreq"]
    times = mkh5raw.times

    chanlocs = pd.DataFrame(
        [
            (
                np.nan,  # theta
                np.nan,  # radius
                ch["ch_name"],  # labels
                np.nan,  # sph_theta
                np.nan,  # sph_phi
                np.nan,  # sph_radius
                ch["loc"][1],  # X for eeglab default
                -1.0 * ch["loc"][0],  # Y for eeglab default
                ch["loc"][2],  # Z
                np.nan,  # ref
                re.match(
                    r".+FIFFV_(?P<kind>.+)_CH.+",  # EEG, EOG, MISC, STIM
                    str(ch["kind"]),
                )["kind"].upper(),
                ch["ch_name"],  # urchan
            )
            for ch in mkh5raw.info["chs"]
        ],
        # EEGLAB chlocs fields
        columns=[
            "theta",
            "radius",
            "labels",
            "sph_theta",
            "sph_phi",
            "sph_radius",
            "X",
            "Y",
            "Z",
            "ref",
            "type",
            "urchan",
        ],
    ).to_records(index=False)

    # always convert MNE annotations to EEGLAB events for dblocks and boundaries
    assert len(mkh5raw.annotations) > 0  # by construction at least one mkh5 dblock tag
    eeglab_events_df = pd.DataFrame(mkh5raw.annotations).drop(columns="orig_time")

    eeglab_events_df["type"] = eeglab_events_df["description"].apply(
        lambda x: "boundary" if "boundary" in x or "BAD" in x.upper() else x
    )
    eeglab_events_df["latency"] = (eeglab_events_df["onset"] * fs + 1).astype(
        int
    )  # matlab 1-base sample
    eeglab_events_df["duration"] = (eeglab_events_df["duration"] * fs).astype(int)
    eeglab_events_df = eeglab_events_df[
        ["type", "latency", "duration", "description", "onset"]
    ]

    # always convert log_evcodes
    log_evcode_idxs = np.where(mkh5raw["log_evcodes"][0].squeeze() != 0)[0].astype(int)
    log_evcodes = mkh5raw["log_evcodes"][0][:, log_evcode_idxs].squeeze().astype(int)
    log_evcodes_df = pd.DataFrame(
        {
            "type": log_evcodes.astype(str),  # else dtype mismatch on merge
            "latency": log_evcode_idxs + 1,  # matlab 1-base
            "duration": int(0),
            "description": "log_evcode",
            "log_evcodes": log_evcodes,
            "mne_raw_tick": log_evcode_idxs,
        }
    )

    # if present, convert mkh5 tagged events to EEGLAB events
    if epochs_name:
        tags_df = pd.DataFrame(
            json.loads(mkh5raw.info["description"])["mkh5_epoch_tables"][epochs_name]
        )
        tags_df.insert(0, "type", tags_df["log_evcodes"].astype(str))
        tags_df.insert(1, "latency", tags_df["mne_raw_tick"] + 1)  # matlab 1-base
        tags_df.insert(2, "duration", 0)
        tags_df["urevent"] = np.arange(len(tags_df))

        # merge event tag columns onto log events on the mne_raw_tick
        # type, latency, duration must be exact match by type to merge columns
        # without duplicating rows. Untagged events get NaN filled for the
        # tag columns

        # tagged event codes must agree with log_evcodes
        assert all(log_evcodes_df["log_evcodes"][
            log_evcodes_df["mne_raw_tick"].isin(tags_df["mne_raw_tick"]).to_numpy()
        ] == tags_df["log_evcodes"].to_numpy()), "tagged events don't match log_evcodes"

        # check before and after merge
        n_log_evcodes = len(log_evcodes_df)

        # clobber and let the merge NaN fill untagged events
        log_evcodes_df.drop(columns="mne_raw_tick", inplace=True)
        log_evcodes_df = log_evcodes_df.merge(tags_df, how="outer")
        assert n_log_evcodes == len(log_evcodes_df), "bad merge for codemap tags"

        # update eeglab event field description w/ epoch table name
        log_evcodes_df.loc[
            ~ pd.isna(log_evcodes_df["mne_raw_tick"]), "description"
        ] = epochs_name

    # combine annotations, event codes, and tags
    eeglab_events_df = eeglab_events_df.merge(log_evcodes_df, how="outer").sort_values(
        "latency"
    )
    eeglab_events = eeglab_events_df.to_records(index=False)
    savemat(
        fname,
        dict(
            EEG=dict(
                data=data,
                setname=str(fname),
                nbchan=data.shape[0],
                pnts=data.shape[1],
                trials=1,
                srate=fs,
                xmin=times[0],
                xmax=times[-1],
                chanlocs=chanlocs,
                event=eeglab_events,
                urevent=eeglab_events,
                icawinv=[],
                icasphere=[],
                icaweights=[],
            )
        ),
        appendmat=False,
    )
    return eeglab_events_df


def mkh5_to_set(
    mkh5_f,
    set_f,
    epochs_name=None,
    garv_annotations=None,
    dblock_paths=None,
    apparatus_yaml=None,
    fail_on_info=False,
    fail_on_montage=True,
    verbose="info",
):

    """Convert an mkh5 data file into MNE raw format

    The mkh5 EEG data event channels in EEG.data. The
    channel info is in EEG.chanlocs.

    The EEG.events and EEG.urevents fields contain:

    * mkh5 dblock paths, EEGLAB event type is the path
    * mkh5 dblock boundaries, EEGLAB event type is "boundary", duration 0
    * log event codes, EEGLAB event type is the code value, duration 0
    * tagged log event codes and tags
    * garv artifact intervals from garv_annotations, EEGLAB event type "boundary"

    are in EE
    paths and boundaries are written to EEGLAB .set events. If
    garv_annotations
    tagstagsevents, and channel info are converted to
    mne.BaseRaw and written to EEGLAB .set format along with the event
    tags in epochs_name and garv_annotations, if any.

    Parameters
    ----------
    mkh5_f: str
        File path to a mkpy.mkh5 HDF5 file

    set_f: str
        File path to the EEGLAB .set file.

    epochs_name : str
        Name of a previously set epochs table in the mkh5 file.

    garv_annotations: None | dict, optional
        event_channel: (str)  # channel name with events to annotate
        tmin, tmax: (float)  # relative to time lock event
        units: "ms" or "s". Defaults to None.

    dblock_paths : None | list of mkh5 datablock paths, optional
        The listed datablock paths will be concatenated in order into
        the mne.Raw. Defaults to None, in which case all the data
        blocks in mkh5 file are concatenated in the order returned by
        :py:meth:`.mkh5.dblock_paths`.

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


    Notes
    -----

    This is a thin wrapper around the mkh5mne file format converter.

    Examples
    -------
    >>>  mkh5eeglab.mkh5_to_set(("sub01.h5", "sub01.set")

    >>> mkh5eeglab.to_set(
            "sub01.h5",
            "sub01.set",
            epochs_name="p3",
            garv_annotations=dict(
                event_channel="p3", tmin=-500, tmax=1500, units="ms"
            )
        )

    """

    mkh5raw = mkh5mne.from_mkh5(
        mkh5_f,
        garv_annotations=garv_annotations,
        dblock_paths=dblock_paths,
        apparatus_yaml=apparatus_yaml,
        fail_on_info=fail_on_info,
        fail_on_montage=fail_on_montage,
        verbose=verbose,
    )

    mkh5raw_to_set(mkh5raw, set_f, epochs_name=epochs_name)
