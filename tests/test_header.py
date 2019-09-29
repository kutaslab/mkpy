from .config import mkpy
from mkpy.mkh5 import mkh5


def test_HeaderIO_update_from_dict_keep_existing():

    # --------------------------- SETUP ---------------------------------
    # create header dictionary with default values for each type
    base_types = mkh5.HeaderIO._mkh5_header_types
    base_dict = {key: item() for key, item in base_types.items()}

    # initialize header with some values
    hio = mkh5.HeaderIO()
    hio._header = {**base_dict, "key1": "A", "key2": "B"}

    # ---------------------------- RUN ----------------------------------
    hio._update_from_dict({"key1": "C", "key3": "D"}, keep_existing=True)

    # --------------------------- CHECK ---------------------------------
    assert hio._header == {**base_dict, "key1": "A", "key2": "B", "key3": "D"}


def test_HeaderIO_update_from_dict_overwrite_existing():

    # --------------------------- SETUP ---------------------------------
    # create header dictionary with default values for each type
    base_types = mkh5.HeaderIO._mkh5_header_types
    base_dict = {key: item() for key, item in base_types.items()}

    # initialize header with some values
    hio = mkh5.HeaderIO()
    hio._header = {**base_dict, "key1": "A", "key2": "B"}

    # ---------------------------- RUN ----------------------------------
    hio._update_from_dict(
        {**base_dict, "key1": "C", "key3": "D"}, keep_existing=False
    )

    # --------------------------- CHECK ---------------------------------
    assert hio._header == {**base_dict, "key1": "C", "key2": "B", "key3": "D"}


def test_HeaderIO_update_from_dict_default():

    # --------------------------- SETUP ---------------------------------
    # create header dictionary with default values for each type
    base_types = mkh5.HeaderIO._mkh5_header_types
    base_dict = {key: item() for key, item in base_types.items()}

    # initialize header with some values
    hio = mkh5.HeaderIO()
    hio._header = {**base_dict, "key1": "A", "key2": "B"}

    # ---------------------------- RUN ----------------------------------
    hio._update_from_dict({"key1": "C", "key3": "D"})

    # --------------------------- CHECK ---------------------------------
    assert hio._header == {**base_dict, "key1": "A", "key2": "B", "key3": "D"}
