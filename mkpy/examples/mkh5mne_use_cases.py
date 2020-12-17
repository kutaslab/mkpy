"""
mkh5mne use cases
=================
"""

# %%
# Set up
# -------

from pathlib import Path
from mkpy import mkh5
from mkpy.io import mkh5mne
MKH5_PATH = Path("mkh5_data")
print(mkh5.__version__)

#%%
# Convert .h5 to mne.Raw

