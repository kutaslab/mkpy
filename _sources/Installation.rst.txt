Installation  (64-bit linux only)
=================================

mkpy is distributed as a conda package for installation into conda
virtual environments (see `Conda environments
<https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/environments.html>`_).
The conda virtual environment and the conda package ecosystem is, at
present, the most generally useful approach for cross-platform
open-source data analysis. If you don't yet have conda installed yet,
the lightweight miniconda3 (see `Miniconda
<https://docs.conda.io/en/latest/miniconda.html>`_) in combination
with the ``mamba`` package (see `mamba docs
<https://mamba.readthedocs.io/en/latest/>`_) installed in the **base
environment** is strongly recommended.

.. note:: As of mkpy v0.2.7 the native conda package dependency solver
   has become unusably slow and unreliable for creating environments
   and installing packages with many dependencies and packages on
   conda-forge. As of mkpy v0.2.7, best practices for installation,
   especially in environments with other Python and R packages are to
   use ``mamba`` with strict conda-forge channel priority.

This version of mkpy is tested with Python 3.7, 3.8, and 3.9 in conda
virtual environments constructed as recommended. Other installations,
e.g., with ``conda`` and different channel priorities may or may not
work.


Install the latest stable release
---------------------------------

Run these commands in a linux terminal window bash shell with a recent
and working ``conda`` and ``mamba`` executables. The named package
channels and their order is important. Replace `mkpy_DDMMYY` with a
sensible environment name. A date string and/or version is not
required but may be useful.

* To install the latest stable version of mkpy and the most recent
  versions of the compatible packages including Python in a fresh
  conda environment:

  .. code-block:: bash

      $ mamba create --name mkpy_DDMMYY mkpy -c conda-forge -c defaults -c kutaslab --strict-channel-priority

* To install mkpy for a specific version of Python, say 3.8:

  .. code-block:: bash

      $ mamba create --name mkpy_DDMMYY python=3.8 mkpy -c conda-forge -c defaults -c kutaslab --strict-channel-priority


* To install mkpy into an existing conda environment:

  .. code-block:: bash
  
      $ conda activate mkpy_DDMMYY
      $ mamba install -c conda-forge -c defaults -c kutaslab --strict-channel-priority



Install a pre-release development version
-----------------------------------------

At times an updated development version of mkpy runs ahead of the
latest stable release and is available for conda installation. Installing
the development version is the same as the release version except for
the specification of the channel and label.

  .. code-block:: bash

      $ mamba create --name mkpy_dev_DDMMYY mkpy -c conda-forge -c defaults -c kutaslablabel/pre-release --strict-channel-priority

.. note::
   It strongly recommended to install development versions into
   a fresh conda environment or risk modifiying an existing working
   environment in unintended and/or undesireable ways with upgraded or
   downgraded dependencies.


Install editable source code (development mode)
-----------------------------------------------

The default installation puts a frozen snapshot of the mkpy package
into the activeenvironment's `site-packages`. If you want to modify
the mkpy source and have the changes show up when you import the
package and call the methods you can install in "development mode".

Best practices are to first use ``mamba create`` to create a new conda
development environment populated with the latest mkpy release,
cython, and mkpy dependencies. Then activate the environment and run
``pip install -e .`` to install mkpy in "development" mode which
replaces the downloaded conda package in the Python
`site-packages/mkpy` directory with a link to your souce code
directory.

First, navigate to the working directory where you plan to edit mkpy.

.. code-block:: bash

    $ mamba create --name mkpy_dev_DDMMYY \
        mkpy cython \
	-c conda-forge -c defaults -c kutaslablabel/pre-release \
	--strict-channel-priority
    $ conda activate mkpy_dev_DDMMYY
    $ git clone https://github.com/kutaslab/mkpy --branch dev --single-branch
    $ cd mkpy
    $ pip install . -e


