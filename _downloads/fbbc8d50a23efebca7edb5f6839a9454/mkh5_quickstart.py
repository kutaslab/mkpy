"""
.. _mkh5_quickstart:



mkh5 Quickstart
===============
"""

# %%
#
# #. In a terminal window use ``mamba`` (recommended) or ``conda`` (if
#    necessary) to install mkpy along with jupyter or jupyterlab
#    into a fresh environment and activate it:
#
#    .. code-block:: bash
#
#       $ mamba create --name mkpy_041221 mkpy jupyterlab \
#            -c kutaslab -c conda-forge -c defaults \
#            --strict-channel-priority
#       $ conda activate mkpy_041221
#
#
# #. In a terminal window navigate to the directory where you want
#    to work and run::
#
#    $ jupyter notebook
#
# #. Open a notebook with a Python 3 kernel and proceed.

# %%
#
# Single subject single session workflow

from mkpy import mkh5 as mkh5

DATA_H5_F = "../mkh5_data/_sub000p3.h5"
data_h5 = mkh5.mkh5(DATA_H5_F)
data_h5.reset_all()

# load the crw, log, and YAML header
data_h5.create_mkdata(
    "sub000",
    "../mkdig_data/sub000p3.crw",
    "../mkdig_data/sub000p3.x.log",
    "../mkdig_data/sub000p3.yhdr",
)

# %%
#
# If calibration pulses are not in the .crw file, append them like so:
data_h5.append_mkdata(
    "sub000",
    "../mkdig_data/sub000c.crw",
    "../mkdig_data/sub000c.log",
    "../mkdig_data/sub000c.yhdr",
)

# Visually check the calibration parameters.
pts, pulse, lo, hi, ccode = 3, 10, -50, 50, 0
fig, ax = data_h5.plotcals(
    DATA_H5_F,
    "sub000",
    n_points=pts,  # pts to average, either side of cursor
    cal_size=pulse,  # uV
    lo_cursor=lo,  # lo_cursor ms
    hi_cursor=hi,  # hi_cursor ms
    cal_ccode=ccode,
)
fig.show()

# %%
#
# Scale the EEG A/D to microvolts.
data_h5.calibrate_mkdata(
    "sub000",
    n_points=pts,
    cal_size=pulse,
    lo_cursor=lo,
    hi_cursor=hi,
    cal_ccode=ccode,
    use_cals=None,
)

# %%
# Examine some header info with :py:meth:`.mkh5.headinfo`
data_h5.headinfo("dblock_0.*samplerate")
data_h5.headinfo("dblock_0.*MiPa")
