Glossary
========

.. glossary::

   HDF5 file
     An HDF5 file is a container for storing a variety of scientific
     data and is composed of two primary types of objects: groups and
     datasets. https://support.hdfgroup.org/HDF5/Tutor/fileorg.html

   HDF5 group
     a grouping structure containing zero or more HDF5 objects,
     together with supporting metadata.
     https://support.hdfgroup.org/HDF5/Tutor/fileorg.html

   HDF5 dataset
     a multidimensional array of data elements, together with
     supporting metadata.
     https://support.hdfgroup.org/HDF5/Tutor/fileorg.html

   HDF5 attribute
     a user-defined HDF5 structure attached to a specific HDF5 dataset
     that provides extra information.
     https://support.hdfgroup.org/HDF5/Tutor/fileorg.html

   HDF5 datatype:
     The building blocks of HDF5 data files. Datatypes are either
     atomic ("no smaller parts") or composite ("aggregations of atomic
     types"). https://support.hdfgroup.org/HDF5/Tutor/datatypes.html.

   HDF5 atomic datatype
     A datatype which cannot be decomposed into smaller datatype
     units: ``integer``, ``float``, ``string``, ``date and time``,
     ``bitfield``, ``reference``, ``opaque``

   HDF5 composite datatype
     An aggregation of atomic data types that is either
       #. a single atomic data type: ``array``, ``variable length``,
       ``enumeration``
       #. a sequence of different atomic data types: ``compound``

   mkpy.mkh5 file
     An mkh5 file is a type of HDF5 file with its HDF5 datasets and
     their attributes named and organized as mkpy.mkh5 ``datablocks``.

   mkpy.mkh5 datablock
     An HDF5 dataset that
     * is named `dblock_N`, for non-negative integer N
     * has an mkpy.mkh5 attribute
     * is a 1-D array of mkpy.mkh5 samples where the `crw_ticks` field of
     the samples is "regular and uninterrupted"

       .. note:: One datablock has all the EEG, header, and location
          information from when the dig recordings starts to when it
          stops or pauses.

   mkpy.mkh5 sample
     an HDF5 compound datatype of named data types containing one
     time-stamped sample of digitized EEG and event code information
     from an ERPSS ``.crw`` and ``.log`` file.
  
     .. todo:: Enumerate the names and types

   mkpy.mkh5 attribute
     an HDF5 attribute containing the key `json_attrs` where its value
     is a legal JSON string enconding an mkh5 header

   mkpy.hmkh5 header
     A key:value document structure containing at least these fields:

     .. todo:: enumerate the header fields

