MNE Python IO (experimental)
==========================================================

.. note::

  Requires mkpy >= 0.2.5 and MNE Python >=0.20 (installed by default
  when mkpy is installed with ``conda``)

The ``mkpy.io.mkh5mne`` module converts .h5 files into MNE Python
``mne.Raw`` continuous EEG recordings and fixed-length ``mne.Epochs``
time-stamped relative to events of interest. This module assumes the
standard mkpy 3D cartesian RAS coordinate space measured in
centimeters.





Quick start
-----------

  Type up a YAML .yhdr file with a mkpy standard apparatus map document.

  Convert the .crw/.log/.yhdr to mkpy .h5 format, tag events with a
  codemap, and set the corresponding fixed-interval epochs as usual.

  .. code-block:: python

     from mkpy import mkh5
     s01 = mkh5.mkh5("s01.h5")

     # the .yhdr YAML file here has an apparatus map
     s01.create("s01", "s01.crw", "s01.log", "s01.yhdr")

     # tag the event codes of interest with the codemap
     tagged_events = s01.get_event_table(my_codemap)

     # time-lock to the tagged events and set the epoch interval
      s01.set_epoch("tagged_epochs", tagged_events, tmin_ms=-500, tmax_ms=1500)


  Convert mkpy EEG to ``mne.Raw`` and ``mne.Epochs`` like so:

   .. code-block:: python

     from mkpy.io import mkh5mne
     s01_raw = mkh5mne.read_raw_mkh5("s01.h5")  # convert mkpy .h5 to mne.Raw
     s01_epochs = mkpy.io.mkh5mne.get_epochs(s01_raw, "tagged_epochs") 

  The mkpy event tags from the codemap are propagated to
  ``s01_epochs.metadata`` and ready for use.

  To convert the garv artifact tags on time-locking events for use in
  MNE data screening, convert them to ``BAD_garv`` mne.Annotations
  like so (see docs
  ::method::`mkh5mne.get_garv_bads()<mkpy.io.mkh5mne.get_garv_bads>`:

     .. code-block:: python

       from mkpy.io import mkh5mne
       s01_raw = mkh5mne.read_raw_mkh5("s01.h5")  # convert mkpy .h5 to mne.Raw
       garv_bads = mkh5mne.get_garv_bads(s01_raw, event_channel="log_evcodes", garv_interval=[-500, 1500, "ms"])



Alternatively, a YAML file containing the apparatus document can
specified as a parameter when the .h5 file is converted to MNE format,
in which case it overrides apparatus information already in the .h5
file.



