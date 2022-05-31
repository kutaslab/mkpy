# Authors: Thomas P. Urbach
#
# License: BSD (3-clause)
#
# to_set based on https://github.com/cbrnr/mnelab/blob/main/mnelab/io/writers.py
# Authors: Clemens Brunner <clemens.brunner@gmail.com>
# License: BSD (3-clause)

import re
import json
import numpy as np

# from numpy.core.records import fromarrays
import pandas as pd
from scipy.io import savemat
from mne import pick_types
from mne.io.constants import FIFF
from mkpy.io import mkh5mne


def mkh5raw_to_set(mkh5raw, fname, epochs_name=None, return_eeglab_events=False):
    """Export mkh5raw EEG, channel, and event data to an EEGLAB .set file.

    Export an mkh5mne.Mkh5Raw instance in memory to an EEGLAB .set
    file. The log events are stored in EEG.events and EEG.urevents and
    any mne.Annotations including garv artifacts are stored there as
    boundary events.  . If `epochs_name` is provided, the mkh5 codemap
    tags for those events are exported as well. Channel locations are
    converted to EEGLAB defaults.

    Parameters
    ----------
    mkh5raw : mkh5mne.Mkh5Raw instance
       As returned by mkh5mne.from_mkh5(), see
       :py:func:`.mkh5mne.from_mkhg` docs for usage.

    fname : str
       Path to the EEGLAB set file to create.

    epochs_name : str, optional
       Include event tags from the named mkh5 epochs table in EEGLAB
       .set events. Defaults to None.

    return_eeglab_events : bool
       If true, also returns the event information injected into the EEGLAB .set file.
       Useful for diagnosis, validataion. Default is False.


    Returns
    -------
    eeglab_events_df : pandas.DataFrame
       Dataframe with the event information exported in the .set


    Examples
    --------

    Minimal: Export EEG data, datablock boundaries, and log events

    >>> from mkpy.io import mkh5mne, mkh5eeglab
    >>>
    >>> mne_raw = mkh5mne.from_mkh5("sub000.h5)
    >>> mkh5eeglab.mkh5raw_to_set(mne_raw, "sub000.set")


    Also export the codemap event tags from mkpy epochs table 'p3'

    >>> mne_raw = mkh5mne.from_mkh5("sub000.h5")
    >>> mkh5eeglab.mkh5raw_to_set(mne_raw, "sub000.set", event_channel="p3")

    """
    data = mkh5raw.get_data()

    # convert eeg, eog to microvolts
    chan_idxs = pick_types(mkh5raw.info, eeg=True, eog=True)
    for chan_idx in chan_idxs:
        chan = mkh5raw.info["chs"][chan_idx]

        # true by mkh5mne construction or die
        assert chan["unit"] == FIFF.FIFF_UNIT_V, f"{chan}"
        assert chan["unit_mul"] == FIFF.FIFF_UNITM_NONE, f"{chan}"
        data[chan_idx, :] *= 1e6

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
        assert all(
            log_evcodes_df["log_evcodes"][
                log_evcodes_df["mne_raw_tick"].isin(tags_df["mne_raw_tick"]).to_numpy()
            ]
            == tags_df["log_evcodes"].to_numpy()
        ), "tagged events don't match log_evcodes"

        # check before and after merge
        n_log_evcodes = len(log_evcodes_df)

        # clobber and let the merge NaN fill untagged events
        log_evcodes_df.drop(columns="mne_raw_tick", inplace=True)
        log_evcodes_df = log_evcodes_df.merge(tags_df, how="outer")
        assert n_log_evcodes == len(log_evcodes_df), "bad merge for codemap tags"

        # update eeglab event field description w/ epoch table name
        log_evcodes_df.loc[
            ~pd.isna(log_evcodes_df["mne_raw_tick"]), "description"
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
    if return_eeglab_events:
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

    The mkh5 EEG data event channels in EEG.data.

    The channel info is in EEG.chanlocs and the mkh5 Right Anterior
    Superior (RAS) coordinates are converted to EEGLAB defaults
    automatically.

    The EEG.events and EEG.urevents fields contain:

    * type field values:
      * log event codes (string representation)
      * "boundary" for datablock boundaries and garv annotations
      * mkh5 dblock path labels
    * latency values:
      * 1-base data sample index of the event in the EEG.data array
    * duration values:
      * log events ar duration 0
      * dblock boundary events are duration 0
      * garv annotation boundary events are garv_annotation tmax - tmin in samples

    Additional event fields are `description` and codemap tags from
    the epochs table, if any.

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

    Minimal

    >>>  mkh5eeglab.mkh5_to_set(("sub01.h5", "sub01.set")

    >>> mkh5eeglab.to_set(
            "sub01.h5",
            "sub01.set",
            "apparatus_yaml"="ras_32_chan_xyz_spherical.yaml",
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
