"""
Electrode location YAML format
==============================
"""

# %%
#
# Electrode locations and fiducial landmarks (optional)
# -----------------------------------------------------
#
# Electrode locations, fiducial landmarks (nasion, left and right
# preauricular points), and head shape data points can be baked into the
# mkpy .h5 data header by including a ``name: apparatus`` YAML document
# in the ``.yhdr`` so that the location information travels with the EEG
#
# The mkh5 standard apparatus specifies a 3D <x, y, z> cartesian
# coordinate space, <right, anterior, superior> (RAS) orientation, with
# measurement units of centimeters.
#
# A minimal apparatus map has the following keys, additional keys may be
# added ad lib.
#
# Addition fields may be added to the maps.
#
# .. code-block:: yaml
#
#    ---
#    # mandatory keys and values
#    name: apparatus
#    space:
#      coordinates: cartesian
#      distance_unit: cm
#      orientation: ras
#
#    # mandatory keys. RAS x, y, z values may vary
#    fiducials:
#      lpa:
#        x: <float>
#        y: <float>
#        z: <float>
#      nasion:
#        x: <float>
#        y: <float>
#        z: <float>
#      rpa:
#        x: <float>
#        y: <float>
#        z: <float>
#
#    # EEG data straems ("channels")
#    streams:
#      label:
#        pos: <sensor_label>
#        neg: <sensor(s) label>
#
#    # ... as needed ...
#
#    # The nmber of electrodes, labels, and x, y, z  values are as needed
#    sensors:
#      label:
#        x: <float>
#        y: <float>
#        z: <float>
#
#    # ... as needed ...
#

# %%
#
# For the current format see :ref:`sample_yhdr`
