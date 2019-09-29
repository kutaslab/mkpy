import re
import yaml
import h5py
import numpy as np
import pandas as pd
from . import h5tools, mkh5


def read_excel_codemap(file, sheet_name=0):
    """Read Excel .xlsx file, return codemap pandas DataFrame."""

    codemap = pd.read_excel(file, sheet_name=sheet_name, index_col="Index")
    if "regexp" not in codemap.columns:
        raise ValueError('"regexp" column must be present.')

    return codemap


def read_txt_codemap(file):
    """Read tab-separated text file, return codemap pandas DataFrame."""

    codemap = pd.read_table(file, index_col="Index")
    if "regexp" not in codemap.columns:
        raise ValueError('"regexp" column must be present.')

    return codemap


def read_yaml_codemap(file):
    """Read YAML file, return codemap pandas DataFrame."""

    with open(file, "r") as f:
        yaml_dict = yaml.load(f)

    _validate_yaml_dict(yaml_dict)

    columns = yaml_dict["columns"]
    rows = yaml_dict["rows"]

    codemap = pd.DataFrame(data=rows, columns=columns).set_index("Index")
    return codemap


def _validate_yaml_dict(yaml_dict):
    """Check validity of YAML file contents."""

    if not isinstance(yaml_dict, dict):
        raise ValueError(
            "YAML file must define a dictionary-like mapping, "
            f"got a {type(yaml_dict)} instead."
        )

    if "columns" not in yaml_dict:
        raise ValueError('YAML file must have a "columns" entry.')

    columns = yaml_dict["columns"]
    if not isinstance(columns, list):
        raise ValueError('"columns" must be a sequence (a list).')

    if "Index" not in columns or "regexp" not in columns:
        raise ValueError('Both "Index" and "regexp" columns must be present.')

    if "rows" not in yaml_dict:
        raise ValueError('YAML file must have a "rows" entry.')

    rows = yaml_dict["rows"]
    if not isinstance(rows, list):
        raise ValueError('"columns" must be a sequence (a list).')

    ncols = len(columns)
    for row in rows:
        if not isinstance(row, list) or len(row) != ncols:
            raise ValueError(
                f"Each row must be a list "
                f"and contain {ncols} items: {columns},\n"
                f"but this row doesn't: {row}."
            )


def find_evcodes(pattern, ticks, evcodes):
    """Run a regular expression search on an array of event codes.

    Parameters
    ----------

    pattern : str
        A regular expression pattern string containing exactly one anchor. For
        a detailed explanation of the format, see notes below.
    ticks, evcodes : NumPy arrays
        Arrays of the same shape containing ticks and event codes of a single
        data block from positions with nonzero event codes. Although the last
        requirement is not mandatory, this is the intended use.

    Returns
    -------

    df : pandas DataFrame
        DataFrame describing matches for the pattern.
    """

    _validate_ticks_and_evcodes(ticks, evcodes)
    _validate_pattern(pattern)

    # the hash denotes the anchor group, we make it named
    pattern = pattern.replace("(#", "(?P<anchor>")

    # group match should align with an alphanumeric word boundary on the right
    pattern = pattern.replace(r")", r"\b)")

    compiled_pattern = re.compile(pattern)

    # this is necessary to identify anchor groups later
    anchor_group_id = compiled_pattern.groupindex["anchor"]

    # convert evcodes to string so we can run regex
    sep = " "
    codestring = sep + sep.join(evcodes.astype(str))

    # map positions in code string to indices in evcodes
    sep_matches = re.finditer(sep, codestring)
    position_to_index = {match.end(): i for i, match in enumerate(sep_matches)}
    assert len(position_to_index) == len(evcodes)

    # run regular expression search on the codestring
    matches = list(re.finditer(compiled_pattern, codestring))

    # collect information about each match aligned with a code
    matches_info = [
        {
            "group": group.strip(),
            "group_id": group_id,
            "group_position": match.start(group_id),
            "match_id": match_id,
        }
        for match_id, match in enumerate(matches)
        # enumerate from index 1, since at 0 we have the universal match group
        for group_id, group in enumerate(match.groups(), 1)
        # match must align with an eventcode position
        if match.start() in position_to_index
    ]

    # check that no group matched more than one code
    if any(len(item["group"].split(" ")) != 1 for item in matches_info):
        raise ValueError("Groups must match one code.")

    # further manipulations are better done in pandas
    df = pd.DataFrame(matches_info)
    if df.empty:
        return df

    # we need to recover indices from code positions in the code string
    indices = df["group_position"].map(position_to_index)
    df["dblock_ticks"] = ticks[indices]
    df["match_code"] = evcodes[indices]
    df["is_anchor"] = df["group_id"] == anchor_group_id

    # verify that matched codes are equal to corresponding evcodes
    assert (df["group"].astype(int) == df["match_code"]).all()
    df.drop(["group", "group_position"], axis=1, inplace=True)

    # derive anchor information
    anchors = df[df["is_anchor"]]
    anchor_data = anchors[["match_id", "dblock_ticks", "match_code"]].rename(
        columns={"dblock_ticks": "anchor_tick", "match_code": "anchor_code"}
    )
    df = df.merge(anchor_data, on="match_id")
    df["anchor_tick_delta"] = df["dblock_ticks"] - df["anchor_tick"]

    return df


def _validate_pattern(pattern):
    """Check that regex pattern conforms to type and format requirements."""

    if not isinstance(pattern, str):
        raise TypeError("Pattern must be a string.")

    if pattern.count("(#") != 1:
        raise ValueError("Pattern must contain exactly one anchor group.")

    if pattern.startswith(" ") or pattern.endswith(" "):
        raise ValueError("Pattern cannot start or end with a whitespace.")

    if 2 * " " in pattern:
        raise ValueError("Pattern cannot contain consecutive whitespaces.")

    return re.compile(pattern)


def _validate_ticks_and_evcodes(ticks, evcodes):
    """Ensure ticks and evcodes are NumPy arrays and have matching shapes."""

    if not isinstance(ticks, np.ndarray):
        raise TypeError(f"ticks must be a NumPy array, not {type(ticks)}.")

    if not isinstance(evcodes, np.ndarray):
        raise TypeError(f"evcodes must be a NumPy array, not {type(evcodes)}.")

    if ticks.shape != evcodes.shape:
        raise ValueError(
            f"ticks and evcodes should have equal shape:\n"
            f"ticks is {ticks.shape}, evcodes is {evcodes.shape}"
        )


def build_event_table(h5_fname, code_map, header_map_f):
    """Construct an event table from the provided codemap and header map file.

    Parameters
    ----------
    h5_fname : str
        HDF5 file name
    code_map : pandas DataFrame
        DataFrame containing at least columns Index and regexp. The regexp
        column specifies regular expressions describing event code patterns.
    header_map_f : str
        header map file name, to be replaced by DataFrame

    Returns
    -------
    event_table : pandas DataFrame
    """

    with h5py.File(h5_fname, "r") as h5:

        # dblock census
        dblocks_and_paths = [
            (h5[dblock_path], dblock_path)
            for dgroup_path in h5tools.get_data_group_paths(h5_fname)
            for dblock_path in h5tools.get_dblock_paths(h5_fname, dgroup_path)
        ]

        # subset every dblock for nonzero event codes
        nonzero = [
            (dblock[dblock["log_evcodes"] != 0], dblock_path)
            for dblock, dblock_path in dblocks_and_paths
        ]

        # build three dataframes
        header_df = build_header_df(dblocks_and_paths, header_map_f)
        match_df = build_match_df(nonzero, code_map)
        dblock_df = build_dblock_df(nonzero)

        # merge them to get the event table
        event_table = match_df.merge(
            header_df, how="left", on="dblock_path"
        ).merge(dblock_df, how="left", on=["dblock_path", "dblock_ticks"])

        # we love pandas, but we want to make sure no information is lost
        # first, we check that no rows from the match_df are missing
        assert len(match_df) == len(event_table)

        # second, we want to make sure the merges were complete in the sense
        # that no values are missing
        assert event_table.notnull().values.all()

        # finally, set epoch information
        event_table["epoch_match_tick_delta"] = 0
        event_table["epoch_ticks"] = 1

        return event_table


def build_match_df(dblocks_and_paths, code_map):
    """Run pattern matcher on dblocks using codemap."""

    match_dfs = (
        (
            find_evcodes(
                row.regexp, db["dblock_ticks"], db["log_evcodes"]
            ).assign(Index=row.Index, dblock_path=dbp)
        )
        for db, dbp in dblocks_and_paths
        for row in code_map.itertuples()
    )

    nonempty_match_dfs = [
        match_df for match_df in match_dfs if not match_df.empty
    ]

    match_df = pd.concat(nonempty_match_dfs, ignore_index=True)
    match_df = match_df.join(code_map, on="Index")

    return match_df


def build_header_df(dblocks_and_paths, header_map_f):
    """Collect header 'slicing' data from given dblocks."""

    hio = mkh5.mkh5.HeaderIO()
    hio.set_slicer(header_map_f)

    header_data = []
    for dblock, dblock_path in dblocks_and_paths:
        hio.get(dblock)
        data = {
            **dict(hio.get_slices()),
            "dblock_path": dblock_path,
            "data_group": dblock.parent.name.lstrip("/"),
            "dblock_srate": hio.header["samplerate"],
        }
        header_data.append(data)

    return pd.DataFrame(header_data)


def build_dblock_df(dblocks_and_paths):
    """Make a DataFrame from a subset of dblock columns."""

    dblock_dfs = [
        pd.DataFrame(dblock).assign(dblock_path=dblock_path)
        for dblock, dblock_path in dblocks_and_paths
    ]

    cols = [
        "dblock_ticks",
        "crw_ticks",
        "raw_evcodes",
        "log_evcodes",
        "log_ccodes",
        "log_flags",
        "dblock_path",
    ]

    dblock_df = pd.concat(dblock_dfs)[cols]

    return dblock_df
