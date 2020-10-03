"""Module mkio.py minor tweak of NJS dig format reader and (avg) writer

Code has four main sections/functions

  1. Setup
  2. Helper functions
  3. Readers
  4. Writers

"""

# --------
# 1. Setup
# --------
import struct
import numpy as np
import gzip
import math
import os
from mkpy._mkh5 import _decompress_crw_chunk
from mkpy import get_ver

# ----------
# 2. Helpers
# ----------

# Derived from erp/include/header.h:
# '<' denotes little-endianness
_header_dtype = np.dtype(
    [
        ("magic", "<u2"),
        ("epoch_len", "<i2"),  # epoch length in msec
        ("nchans", "<i2"),  # number of channels
        ("sums", "<i2"),  # 0 = ERP, 1 = single trial
        # ^^ 8 bytes
        ("tpfuncs", "<i2"),  # number of processing funcs
        ("pp10uv", "<i2"),  # points / 10 uV
        ("verpos", "<i2"),  # positive point positive voltage, -1 => opposite
        ("odelay", "<i2"),  # ms from trigger to stim (8 video, 4 audio)
        # ^^ 16 bytes
        ("totevnt", "<i2"),  # "total log events"
        ("10usec_per_tick", "<i2"),
        ("time", "<i4"),  # "time in sample clock ticks"
        # ^^ 24 bytes
        ("cond_code", "<i2"),
        ("presam", "<i2"),  # pre-event time in epoch in msec
        ("trfuncs", "<i2"),  # number of rejection functions
        ("totrr", "<i2"),  # total raw records including rejects
        # ^^ 32 bytes
        ("totrej", "<i2"),  # total raw rejects
        ("sbcode", "<i2"),  # "subcondition number (bin number)"
        ("cprecis", "<i2"),  # channel precision in # of 256 points blocks
        ("dummy1", "<i2"),  # placeholder for ovf_errors (see header)
        # ^^ 40 bytes
        ("decfact", "<i2"),  # decimation factor used in processing
        ("dh_flag", "<i2"),  # sets time resolution (see header defines)
        ("dh_item", "<i4"),  # sequential item #
        # ^^ 48 bytes
        ("rfcnts", "<i2", (8,)),  # ndividual rejection counts 8 poss. rfs
        ("rftypes", "S64"),  # 8 char. descs for 8 poss. rfs
        ("chndes", "S128"),
        ("subdes", "S40"),
        ("sbcdes", "S40"),
        ("condes", "S40"),
        ("expdes", "S40"),
        ("pftypes", "S24"),
        ("chndes2", "S40"),
        ("flags", "<u2"),  # see flag values in header
        ("nrawrecs", "<u2"),  # raw records if this is a raw file header
        ("idxofflow", "<u2"),
        ("idxoffhi", "<u2"),
        ("chndes3", "S24"),  # channel description size
    ]
)

# If, say, chndes has trailing null bytes, then rec["chndes"] will give us a
# less-than-128-byte string back. But this function always gives us the full
# 128 byte string, trailing nuls and all.
def _get_full_string(record, key):
    val = record[key]
    desired_len = record.dtype.fields[key][0].itemsize
    return val + (desired_len - len(val)) * b"\x00"  # TPU forced to byte


def _gzipped(stream):
    """Return True if stream is a gzip file."""

    initial_pos = stream.tell()
    gzip_magic = b"\x1f\x8b"
    file_magic = stream.read(2)
    stream.seek(initial_pos)  # rewind back 2 bytes

    return file_magic == gzip_magic


def _get_reader_for_magic(magic):
    """Return appropriate reader function based on the magic."""

    if magic == 0x17A5:
        return _read_raw_chunk
    elif magic == 0x97A5:
        return _read_compressed_chunk
    else:
        return None


def _is_valid_samplerate(hz):
    """Return True if sample rate is close to an integer, False otherwise."""

    closest_integer = round(hz, 0)

    if not math.isclose(hz, closest_integer, abs_tol=1e-6):
        return False
    else:
        return True


def _get_channel_names(header):
    """Extract list of channel names from header."""

    if header["nchans"] <= 16:
        dtype = "S8"
    elif header["nchans"] <= 32:
        dtype = "S4"
    else:
        raise NotImplementedError(
            "Channel name extraction for large " "montages not yet supported"
        )

    # return np.fromstring(_get_full_string(header, 'chndes'), dtype=dtype)
    return np.frombuffer(_get_full_string(header, "chndes"), dtype=dtype)


# -------
# Readers
# -------
def _read_header(stream):
    """Read header (the first 512 bytes) from file, return a subset of it.

    Parameters
    ----------
    stream : filestream
        .raw or .crw filestream

    Returns
    -------
    (reader, header["nchans"], hz, channel_names, info) : tuple

    where
        reader : function
            _read_raw_chunk or _read_compressed_chunk
        header["nchans"] : int
            number of data channels
        hz : float
            sampling frequency in samples per second
        channel_names : NumPy array of binary strings
            channel name codes, e.g. MiPf, LLPf, etc.
        info : dict
            dictionary with keys:
                name, magic, subdesc, expdesc,
                odelay, samplerate, recordduration,
                recordsize, nrawrecs, nchans
    """

    # read header from file and build NumPy data structure
    header_str = stream.read(512)

    # fromstring deprecated b.c. strange behavior on unicode
    # header = np.fromstring(header_str, dtype=_header_dtype)[0]
    header = np.frombuffer(header_str, dtype=_header_dtype)[0]

    # determine appropriate reader function
    reader = _get_reader_for_magic(header["magic"])
    if reader is None:
        raise ValueError(f'Bad magic number: {hex(header["magic"])}.')

    # calculate and validate sample rate
    hz = 1 / (header["10usec_per_tick"] / 100_000)
    if not _is_valid_samplerate(hz):
        raise ValueError(f"File claims weird non integer sample rate: {hz}.")

    # extract channel name codes from header
    channel_names = _get_channel_names(header)

    # capture complete and jsonifiable. new in 0.2.4
    raw_dig_header = dict()
    for key in header.dtype.names:
        val = header[key]
        if np.isscalar(val):
            val = val.item().decode("utf-8") if isinstance(val, bytes) else val.item()
        else:
            val = val.tolist()
        raw_dig_header[key] = val

    info = dict(
        {
            "name": "dig",
            "magic": header["magic"],
            "subdesc": header["subdes"],
            "expdesc": header["expdes"],
            "odelay": header["odelay"],
            "samplerate": hz,
            "recordduration": 256 / hz,
            "recordsize": 256,
            "nrawrecs": header["nrawrecs"],
            "nchans": header["nchans"],
            "mkh5_version": get_ver(),  # new in 0.2.4
            "raw_dig_header": raw_dig_header,
        }
    )

    return reader, header["nchans"], channel_names, info


def read_raw(stream, dtype):
    """parses bytestream of from kutaslab eeg file into usable data

    Returns
    -------
      (channel_names, np.array(all_codes, dtype=np.int16),
                        np.array(record_counts, dtype=np.int16),
                        final_data, info)

    all_codes -- a vector of event codes and record indices from the mark track
    final_data -- a np.array: samples (rows) x eeg channels (columns)

    """
    if _gzipped(stream):
        stream = gzip.GzipFile(mode="r", fileobj=stream)

    reader, nchans, channel_names, info = _read_header(stream)
    # NJS. Data is stored in a series of "chunks" -- each chunk
    # contains 256 s16 samples from each channel (the 32/64/whatever
    # analog channels, plus 1 channel for codes -- that channel being
    # first.).  The code channel contains a "record number" as its
    # first entry in each chunk, which simply increments by 1 each
    # time.
    all_codes = []
    data_chunks = []
    chunk_bytes = (nchans + 1) * 512
    chunkno = 0
    record_counts = []
    while True:
        read = reader(stream, nchans)
        if read is None:
            break
        (codes_chunk, data_chunk) = read
        assert len(codes_chunk) == 256
        assert data_chunk.shape == (256 * nchans,)
        assert codes_chunk[0] == chunkno

        # codes_chunk[0] = 65535 ## NJS overwrote record counter
        record_counts.append(
            codes_chunk[0]
        )  # track for sanity checks and later processing
        codes_chunk[
            0
        ] = 0  # clear the record count so marktrack has all and only event codes TPU
        all_codes += codes_chunk
        data_chunk.resize((256, nchans))
        data_chunks.append(np.array(data_chunk, dtype=dtype))
        chunkno += 1

    final_data = np.vstack(data_chunks)

    # TPU ... changed all_codes, dtype=np.uint16 -> np.int16
    all_codes = np.array(all_codes, dtype=np.int16)
    return channel_names, all_codes, record_counts, final_data, info


def _read_raw_chunk(stream, nchans):
    """reads a kutaslab .raw eeg data record bytestream, returns 
    (mark track event codes, vector of eeg data)

    """
    chunk_bytes = (nchans + 1) * 512
    buf = stream.read(chunk_bytes)
    # Check for EOF:
    if not buf:
        return None
    codes_list = list(struct.unpack("<256H", buf[:512]))
    # data_chunk = np.fromstring(buf[512:], dtype="<i2")
    data_chunk = np.frombuffer(buf[512:], dtype="<i2")
    return (codes_list, data_chunk)


def _read_compressed_chunk(stream, nchans):
    """decompresses record of kutaslab .crw eeg data bytestream"""
    # Check for EOF:
    ncode_records_minus_one_buf = stream.read(1)
    if not ncode_records_minus_one_buf:
        return None
    # Code track (run length encoded):
    (ncode_records_minus_one,) = struct.unpack("<B", ncode_records_minus_one_buf)
    ncode_records = ncode_records_minus_one + 1
    code_records = []
    for i in range(ncode_records):
        code_records.append(struct.unpack("<BH", stream.read(3)))
    codes_list = []
    for (repeat_minus_one, code) in code_records:
        codes_list += [code] * (repeat_minus_one + 1)
    assert len(codes_list) == 256
    # Data bytes (delta encoded and packed into variable-length integers):
    (ncompressed_words,) = struct.unpack("<H", stream.read(2))
    compressed_data = stream.read(ncompressed_words * 2)
    data_chunk = _decompress_crw_chunk(compressed_data, ncompressed_words, nchans)
    return (codes_list, data_chunk)


def read_log(fo):
    """generator reads kutaslab binary log, returns (code, tick, condition, flag)

    Parameters
    ----------
    fo : file object

    flags values
        # avg -x sets 0 = OK, 20 = artifact, 40 = polinv, 60 = polinv + artifact
        # cdbl -op also sets flags according to the bdf
        # 100 = data error (rare)
    """
    while True:
        event = fo.read(8)
        if not event:
            return
        # NJS
        # (code, tick_hi, tick_lo, condition, flag) \
        #     = struct.unpack("<HHHBB", event)

        # TPU ... 2-byte event codes can be negative, i.e. short
        (code, tick_hi, tick_lo, condition, flag) = struct.unpack("<hHHBB", event)

        yield (code, (tick_hi << 16 | tick_lo), condition, flag)  # NJS


def load(
    f_raw, f_log, dtype=np.float64, delete_channels=[], calibrate=True, **kwargs,
):

    # read the raw and sanity check the records ...
    channel_names, raw_codes, record_counts, data, info = read_raw(f_raw, dtype)
    assert all(record_counts == np.arange(len(record_counts)))

    # read the log
    codes_from_log = np.zeros(raw_codes.shape, dtype=raw_codes.dtype)
    for (code, tick, condition, flag) in read_log(f_log):
        codes_from_log[tick] = code
    discrepancies = codes_from_log != raw_codes
    assert (codes_from_log[discrepancies] == 0).all()
    assert (raw_codes[discrepancies] == 65535).all()
    if delete_channels:  # fast-path: no need to do a copy if nothing to delete
        keep_channels = []
        for i in range(len(channel_names)):
            if channel_names[i] not in delete_channels:
                keep_channels.append(i)
        assert len(keep_channels) + len(delete_channels) == len(channel_names)
        data = data[:, keep_channels]
        channel_names = channel_names[keep_channels]
    if calibrate:
        calibrate_in_place(data, raw_codes, **kwargs)
    return channel_names, raw_codes, data, info


# -------
# Writers
# -------

# To write multiple "bins" to the same file, just call this function
# repeatedly on the same stream.

# NJS
def write_erp_as_avg(erp, stream):
    magic = "\xa5\x17"
    header = np.zeros(1, dtype=_header_dtype)[0]
    header["magic"] = 0x17A5
    header["verpos"] = 1
    # One avg record is always exactly 256 * cprecis samples long, with
    # cprecis = 1, 2, 3 (limitation of the data format).  So we pick the
    # smallest cprecis that is <= our actual number of samples (maximum 3),
    # and then we resample to have that many samples exactly.  (I.e., we try
    # to resample up when possible.)  The kutaslab tools only do
    # integer-factor downsampling (decimation), and they write the decimation
    # factor to the file.  I don't see how it matters for the .avg file to
    # retain the decimation information, and the file won't let us write down
    # upsampling (especially non-integer upsampling!), so we just set our
    # decimation factor to 1 and be done with it.
    if erp.data.shape[0] <= 1 * 256:
        cprecis = 1
    elif erp.data.shape[0] <= 2 * 256:
        cprecis = 2
    elif erp.data.shape[0] <= 3 * 256:
        cprecis = 3
    else:
        raise ValueError("cprecis > 3")  ## TPU

    samples = cprecis * 256
    if erp.data.shape[0] != samples:
        import scipy.signal

        resampled_data = scipy.signal.resample(erp.data, samples)
    else:
        resampled_data = erp.data
    assert resampled_data.shape == (samples, erp.data.shape[1])
    resampled_sp_10us = int(
        round((erp.times.max() - erp.times.min()) * 100.0 / samples)
    )
    epoch_len_ms = int(round(samples * resampled_sp_10us / 100.0))

    # Need to convert to s16's. To preserve as much resolution as possible,
    # we use the full s16 range, minus a bit to make sure we don't run into
    # any overflow issues.
    s16_max = 2 ** 15 - 10
    # Same as np.abs(data).max(), but without copying the whole array:
    data_max = max(resampled_data.max(), np.abs(resampled_data.min()))
    # We have to write the conversion factor as an integer, so we round it
    # down here, and then use the *rounded* version to actually convert the
    # data.
    s16_per_10uV = int(s16_max / (data_max / 10))
    # Except that if our conversion factor itself overflows, then we have to
    # truncate it back down (and lose a bit of resolution in the process, oh
    # well):
    if s16_per_10uV > s16_max:
        s16_per_10uV = s16_max
    integer_data = np.array(np.round(s16_per_10uV * resampled_data / 10.0), dtype="<i2")

    header["epoch_len"] = epoch_len_ms
    header["nchans"] = integer_data.shape[1]
    header["sums"] = 0  # ERP
    header["tpfuncs"] = 1  # processing function of "averaging"
    header["pftypes"] = "average"
    header["pp10uv"] = s16_per_10uV
    header["10usec_per_tick"] = resampled_sp_10us
    header["presam"] = 0 - erp.times.min()
    header["cprecis"] = cprecis
    header["decfact"] = 1

    if "num_combined_trials" in erp.metadata:
        header["totrr"] = erp.metadata["num_combined_trials"]

    if len(erp.channel_names) <= 16:
        header["chndes"] = np.asarray(erp.channel_names, dtype="S8").tostring()
    elif len(erp.channel_names) <= 32:
        header["chndes"] = np.asarray(erp.channel_names, dtype="S4").tostring()
    else:
        assert False, "Channel name writing for large montages not yet supported"
    if "experiment" in erp.metadata:
        header["expdes"] = erp.metadata["experiment"]
    if "subject" in erp.metadata:
        header["subdes"] = erp.metadata["subject"]
    if erp.name is not None:
        header["condes"] = erp.name

    header.tofile(stream)
    # avg files omit the mark track.  And, all the data for a single channel
    # goes together in a single chunk, rather than interleaving all channels.
    # THIS IS DIFFERENT FROM RAW FILES!
    for i in range(integer_data.shape[1]):
        integer_data[:, i].tofile(stream)


if __name__ == "__main__":
    # stub
    pass
