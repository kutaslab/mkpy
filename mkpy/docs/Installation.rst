Installation
============

Installing the latest stable mkpy with ``conda`` is strongly
recommended. If you don't have conda installed yet, miniconda3
(https://docs.conda.io/en/latest/miniconda.html#installing) is the way
to go.

As of v0.2.4+, conda installed mkpy runs with Python 3.6, 3.7, and
3.8.


Conda install latest stable release (recommended)
-------------------------------------------------

Run these commands in a linux terminal window bash shell. The named
conda channels and their order is important. Replace `some_env` with a
sensible environment name.

* Install he latest stable version of ``mkpy`` and the most recent
  versions of the compatible packages including Python in a fresh
  conda environment:

  .. code-block:: bash

      create conda -n some_env -c kutaslab -c defaults -c conda-forge mkpy

* Install for a specific version of Python, say 3.7:

  .. code-block:: bash

      create conda -n some_env -c kutaslab -c defaults -c conda-forge python=3.7 mkpy


* Install into an existing `conda` environment:

  .. code-block:: bash
  
      conda activate some_env
      conda install  -c kutaslab -c defaults -c conda-forge mkpy


Conda install a pre-release development version
-----------------------------------------------

* At times a development version of mkpy runs ahead of the latest
  stable release and is available for conda installation.  It is
  strongly recommended to install development versions into a fresh
  conda environment or risk modifiying an existing working environment
  in unintended and/or undesireable ways with upgraded or downgraded
  dependencies.

  .. code-block:: bash

      create conda -n dev_env -c kutaslab/label/pre-release -c defaults -c conda-forge mkpy


Install from source
-------------------

Clone the github repository into the current directory and run
setup.py. Good luck. 

.. code-block:: bash

   git clone https://github.com/kutaslab/mkpy



pip installation from PyPI: not supported
-----------------------------------------


