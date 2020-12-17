"""
mkh5 common use cases
=====================
"""

# %%
# Set up
# -------

from pathlib import Path
from mkpy import mkh5
MKDIG_PATH = Path("mkdig_data")

print(mkh5.__version__)

# %%
# One sbject, separate cals
# -------------------------
#
# Use :meth:`mkh5.append_mkdata()<mkpy.mkh5.mkh5.append_mkdata>` to
# combine EEG recordings  and separately recorded calibration data in 
# a single .h5 file prior to converting A/D samples to :math:`\mu`V.


# %%
# Set EEG and calibration data file names
crw = MKDIG_PATH / "sub000p3.crw"    # EEG recording
log = MKDIG_PATH / "sub000p3.x.log"  # events
yhdr = MKDIG_PATH / "sub000p3.yhdr"  # extra header info

cals_crw = MKDIG_PATH / "sub000c.crw"
cals_log = MKDIG_PATH / "sub000c.log"
cals_yhdr = MKDIG_PATH / "sub000c.yhdr"


# %%
# Convert .crw/.log to mkh5 format .h5.
p3_h5_f =  "example_sub000p3.h5"
p3_h5 = mkh5.mkh5(p3_h5_f)
p3_h5.reset_all()
p3_h5.create_mkdata("sub000", crw, log, yhdr)

# %%
# Append calibration data to the existing ``sub000``.
p3_h5.append_mkdata("sub000", cals_crw, cals_log, cals_yhdr)

# %%
# Convert EEG and calibration data A/D to microvolts.
pts, pulse, lo, hi, ccode = 5, 10, -40, 40, 0
p3_h5.calibrate_mkdata(
    "sub000",  # data group to calibrate with these cal pulses
    n_points=pts,  # samples to average
    cal_size=pulse,  # uV
    lo_cursor=lo,  # lo_cursor ms
    hi_cursor=hi,  # hi_cursor ms
    cal_ccode=ccode,  # condition code
)
