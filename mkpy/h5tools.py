""":meta private:"""

import h5py


def get_data_group_paths(h5f):
    """Return paths to all data groups that contain a dblock_0.

    The paths are sorted lexicographically.

    Parameters
    -----------
    h5f : str
        HDF5 file name

    Returns
    -------
    group_paths : list of str
        List of paths to data groups
    """

    group_paths = []

    def group_criterion(name, obj):
        if isinstance(obj, h5py.Group) and "dblock_0" in obj:
            group_paths.append(name)

    with h5py.File(h5f, "r") as h5:
        h5.visititems(group_criterion)

    return sorted(group_paths)


def get_dblock_paths(h5f, h5_path):
    """Get dblock_N paths, in acquisition order, for the group at h5_path.

    Parameters
    -----------
    h5f : str
        HDF5 file name
    h5_path : str
        Path to group under `h5f` containing dblocks

    Returns
    -------
    dblock_paths : list of str
        List of paths to dblocks


    Examples

    >>> from mkpy import h5tools
    >>> h5tools.get_dblock_paths('calstest.h5', 'calstest')
    ['calstest/dblock_0',
     'calstest/dblock_1',
     'calstest/dblock_2',
     'calstest/dblock_3',
     'calstest/dblock_4']

    """

    with h5py.File(h5f, "r") as h5:

        if h5_path not in h5.keys():
            msg = f'Group "{h5_path}" does not exist.'
            raise ValueError(msg)

        dblocks_found = [d for d in h5[h5_path].keys() if "dblock" in d]

        if not dblocks_found:
            msg = f"No dblocks found under {h5f}/{h5_path}."
            raise ValueError(msg)

    # dblocks should be contiguously numbered 0, ..., n-1
    n_dblocks = len(dblocks_found)
    dblocks_expected = [f"dblock_{i}" for i in range(n_dblocks)]

    if set(dblocks_found) != set(dblocks_expected):
        msg = f"Disordered dblocks in {h5f}/{h5_path}: "
        msg += ", ".join(dblocks_found)
        raise ValueError(msg)

    # dblocks_expected is sorted and equal to found, so we use it
    dblock_paths = [f"{h5_path}/{dblock}" for dblock in dblocks_expected]

    return dblock_paths
