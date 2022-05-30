"""Test module for mkpy I/O functionality."""

import os.path
import glob
import io
import numpy as np
import pytest

from .config import TEST_DIR, mkpy
from mkpy import mkio
from mkpy import get_ver

__version__ = get_ver()


def fetch_test_dir():
    return os.path.join(os.path.dirname(__file__))


# For debugging
def assert_files_match(p1, p2):
    # TPU open() vs. io.open() bytes v. (encoded) text streams differs
    # py2 v py3 (hz1, channames1, codes1, data1, info1) =
    # read_raw(open(p1), "u2") (hz2, channames2, codes2, data2, info2)
    # = read_raw(open(p2), "u2")
    channames1, codes1, record_counts1, data1, info1 = mkio.read_raw(
        open(p1, "rb"), "i2"
    )
    channames2, codes2, record_counts2, data2, info2 = mkio.read_raw(
        open(p2, "rb"), "i2"
    )
    assert (channames1 == channames2).all()
    assert (codes1 == codes2).all()
    assert record_counts1 == record_counts2
    assert (data1 == data2).all()
    # info is a list of ['key_string', numpy_value]
    z = list(zip(info1, info2))
    assert len(info1) == len(info2) == len(z)
    for k in z:
        # keys should be scalars ...
        assert k[0][0] == k[1][0]
        # values might be arrays
        if isinstance(k[0][1] == k[1][1], bool):
            assert k[0][1] == k[1][1]
        else:
            assert (k[0][1] == k[1][1]).all()


def compare_raw_to_crw(raw_stream, crw_stream):
    raw_reader, raw_nchans, raw_hz, raw_names, raw_l = _read_header(raw_stream)
    crw_reader, crw_nchans, crw_hz, crw_names, crw_l = _read_header(crw_stream)
    assert raw_reader is _read_raw_chunk
    assert crw_reader is _read_compressed_chunk
    assert raw_nchans == crw_nchans
    assert raw_hz == crw_hz
    assert raw_names == crw_names
    assert crw_l is None
    while True:
        raw_start = raw_stream.tell()
        raw_chunk = _read_raw_chunk(raw_stream, raw_nchans)
        raw_end = raw_stream.tell()
        crw_start = crw_stream.tell()
        crw_chunk = _read_compressed_chunk(crw_stream, crw_nchans)
        crw_end = crw_stream.tell()
        assert (raw_chunk is None) == (crw_chunk is None)
        if raw_chunk is None:
            break
        (raw_codes, raw_data) = raw_chunk
        (crw_codes, crw_data) = crw_chunk
        problems = []
        if raw_codes != crw_codes:
            problems.append("codes")
        if tuple(raw_data) != tuple(crw_data):
            problems.append("data")
        if problems:
            print(
                (
                    "Bad %s! raw: [%s, %s], crw: [%s, %s]"
                    % (problems, raw_start, raw_end, crw_start, crw_end)
                )
            )
            assert False


# -------
# tests
# -------
def test_read_header_compressed_and_raw():
    """Test _read_header on .crw and .raw files against a hand-computed output.

    The input data is in the body of this test, so no true file IO is needed,
    but it is simulated via io.BytesIO.

    * Structure

      1. Input definition.
      2. Expected output definition.
      3. Run _read_header and compare outputs.

    * Where is the input data coming from?

      The header below is the output of

      ```xxd -l 512 -p mkpy/tests/data/one-chunk.crw```

      the first 512 bytes of `one-chunk.crw`.

      No endianness adjustments are performed, the data is raw.


    * Where is the expected output coming from?

      The output is hand computed, see notebook 'Test_mkio_read_header' under
      tests/Notebooks.

    """

    # -----------------------------------------------------------------------#
    #                               INPUT DATA                               #
    # -----------------------------------------------------------------------#

    raw_magic = bytes.fromhex("a517")
    crw_magic = bytes.fromhex("a597")

    # note magic is missing here
    header_body = bytes.fromhex(
        "0000"
        "2000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0800"
        "0000"
        "9001"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0100"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "6c6c"
        "6500"
        "6c68"
        "7a00"
        "4d69"
        "5066"
        "4c4c"
        "5066"
        "524c"
        "5066"
        "4c4d"
        "5066"
        "524d"
        "5066"
        "4c44"
        "4672"
        "5244"
        "4672"
        "4c4c"
        "4672"
        "524c"
        "4672"
        "4c4d"
        "4672"
        "524d"
        "4672"
        "4c4d"
        "4365"
        "524d"
        "4365"
        "4d69"
        "4365"
        "4d69"
        "5061"
        "4c44"
        "4365"
        "5244"
        "4365"
        "4c44"
        "5061"
        "5244"
        "5061"
        "4c4d"
        "4f63"
        "524d"
        "4f63"
        "4c4c"
        "5465"
        "524c"
        "5465"
        "4c4c"
        "4f63"
        "524c"
        "4f63"
        "4d69"
        "4f63"
        "4132"
        "0000"
        "4845"
        "4f47"
        "726c"
        "6500"
        "7268"
        "7a00"
        "5375"
        "626a"
        "6563"
        "7420"
        "7033"
        "2032"
        "3030"
        "382d"
        "3038"
        "2d32"
        "3000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "6272"
        "6f77"
        "6e2d"
        "3100"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
        "0000"
    )

    # -----------------------------------------------------------------------#
    #                     EXPECTED OUTPUT DEFINITIONS                        #
    # -----------------------------------------------------------------------#

    expected_COMPRESSED_reader = mkio._read_compressed_chunk
    expected_RAW_reader = mkio._read_raw_chunk

    expected_nchans = 32

    # calculation of hz
    tens_of_microseconds_per_tick = 400
    microseconds_per_tick = 10 * tens_of_microseconds_per_tick
    seconds_per_tick = microseconds_per_tick / 1000000

    expected_hz = 1 / seconds_per_tick

    expected_channel_names = np.array(
        [
            b"lle",
            b"lhz",
            b"MiPf",
            b"LLPf",
            b"RLPf",
            b"LMPf",
            b"RMPf",
            b"LDFr",
            b"RDFr",
            b"LLFr",
            b"RLFr",
            b"LMFr",
            b"RMFr",
            b"LMCe",
            b"RMCe",
            b"MiCe",
            b"MiPa",
            b"LDCe",
            b"RDCe",
            b"LDPa",
            b"RDPa",
            b"LMOc",
            b"RMOc",
            b"LLTe",
            b"RLTe",
            b"LLOc",
            b"RLOc",
            b"MiOc",
            b"A2",
            b"HEOG",
            b"rle",
            b"rhz",
        ],
        dtype="|S4",
    )

    # expected_info = {
    #     "name": "dig",
    #     "magic": None,  # to be defined right before test time
    #     "subdesc": b"Subject p3 2008-08-20",
    #     "expdesc": b"brown-1",
    #     "odelay": 8,
    #     "samplerate": expected_hz,
    #     "recordduration": 256 * seconds_per_tick,  # see calculation of hz
    #     "recordsize": 256,
    #     "nrawrecs": 0,  # in this case
    #     "nchans": expected_nchans,
    # }

    expected_info = {
        "name": "dig",
        "magic": None,  # hardcoded at test
        "subdesc": b"Subject p3 2008-08-20",
        "expdesc": b"brown-1",
        "odelay": 8,
        "samplerate": 250.0,
        "recordduration": 1.024,
        "recordsize": 256,
        "nrawrecs": 0,
        "nchans": 32,
        "mkh5_version": __version__,  # new in 0.2.4
        "raw_dig_header": {
            "magic": None,  # harcoded at test
            "epoch_len": 0,
            "nchans": 32,
            "sums": 0,
            "tpfuncs": 0,
            "pp10uv": 0,
            "verpos": 0,
            "odelay": 8,
            "totevnt": 0,
            "10usec_per_tick": 400,
            "time": 0,
            "cond_code": 0,
            "presam": 0,
            "trfuncs": 0,
            "totrr": 0,
            "totrej": 0,
            "sbcode": 0,
            "cprecis": 1,
            "dummy1": 0,
            "decfact": 0,
            "dh_flag": 0,
            "dh_item": 0,
            "rfcnts": [0, 0, 0, 0, 0, 0, 0, 0],
            "rftypes": "",
            "chndes": "lle\x00lhz\x00MiPfLLPfRLPfLMPfRMPfLDFrRDFrLLFrRLFrLMFrRMFrLMCeRMCeMiCeMiPaLDCeRDCeLDPaRDPaLMOcRMOcLLTeRLTeLLOcRLOcMiOcA2\x00\x00HEOGrle\x00rhz",
            "subdes": "Subject p3 2008-08-20",
            "sbcdes": "",
            "condes": "",
            "expdes": "brown-1",
            "pftypes": "",
            "chndes2": "",
            "flags": 0,
            "nrawrecs": 0,
            "idxofflow": 0,
            "idxoffhi": 0,
            "chndes3": "",
        },
    }

    # -----------------------------------------------------------------------#
    #                             TEST RAW                                   #
    # -----------------------------------------------------------------------#

    raw_file = io.BytesIO(raw_magic + header_body)

    # run _read_header
    (
        actual_RAW_reader,
        actual_nchans,
        actual_channel_names,
        actual_info,
    ) = mkio._read_header(raw_file)

    actual_magic = actual_info["raw_dig_header"]["magic"]
    assert actual_magic == 0x17A5
    expected_info["magic"] = expected_info["raw_dig_header"]["magic"] = actual_magic
    assert expected_info == actual_info
    assert expected_nchans == actual_nchans
    assert expected_RAW_reader == actual_RAW_reader
    assert np.array_equal(expected_channel_names, actual_channel_names)

    # ------------------------------------------------------------------------#
    #                           TEST COMPRESSED                               #
    # ------------------------------------------------------------------------#

    crw_file = io.BytesIO(crw_magic + header_body)

    # run _read_header
    (
        actual_COMPRESSED_reader,
        actual_nchans,
        actual_channel_names,
        actual_info,
    ) = mkio._read_header(crw_file)

    actual_magic = actual_info["raw_dig_header"]["magic"]
    assert actual_magic == 0x97A5
    expected_info["magic"] = expected_info["raw_dig_header"]["magic"] = actual_magic
    for key, val in actual_info.items():
        print("actual", key, val)
        try:
            assert val == expected_info[key]
        except:
            print("expected", key, expected_info[key])
            import pdb

            pdb.set_trace()
            pass

    assert expected_info == actual_info
    assert expected_nchans == actual_nchans
    assert expected_COMPRESSED_reader == actual_COMPRESSED_reader
    assert np.array_equal(expected_channel_names, actual_channel_names)


def test_read_header_bad_magic():
    """_read_header must raise ValueError on input with a bad magic."""

    bad_input = 512 * b"\x00"
    file = io.BytesIO(bad_input)

    with pytest.raises(ValueError):
        mkio._read_header(file)


def test_read_raw_crw():
    """NJS's original test for .raw, .raw.gz, .crw files.
    TPU tweaked for read_raw returning the additional record counts
    and dropped test for gzip.

    .raw and .crw kutaslab file types must be present in the
    ./data directory
    """

    # test_dir = fetch_test_dir() + "/data/"
    data_dir = TEST_DIR("data")
    test_files = glob.glob(os.path.join(data_dir, "*.raw"))
    tested = 0
    for rawp in test_files:
        crwp = rawp[:-3] + "crw"
        print(rawp, crwp)
        assert_files_match(rawp, crwp)

        # TPU DEPRECATED support for .gz
        # print(rawp, rawp + ".gz")
        # assert_files_match(rawp, rawp + ".gz")
        tested += 1
    # Cross-check, to make sure is actually finding the files... (bump up this
    # number if you add more test files):
    assert tested == 3, "Should be 3 test_files: {0}".format(test_files)
