Installation (64-bit linux only)
================================

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

* Install the latest stable version of ``mkpy`` and the most recent
  versions of the compatible packages including Python in a fresh
  conda environment:

  .. code-block:: bash

      conda create --name some_env mkpy -c kutaslab -c defaults -c conda-forge

* Install for a specific version of Python, say 3.7:

  .. code-block:: bash

      conda create --name some_env python=3.7 mkpy -c kutaslab -c defaults -c conda-forge


* Install into an existing conda environment:

  .. code-block:: bash
  
      conda activate some_env
      conda install -c kutaslab -c defaults -c conda-forge mkpy


Conda install a pre-release development version
-----------------------------------------------

* At times an updated development version of mkpy runs ahead of the
  latest stable release and is available for conda installation.  It
  is strongly recommended to install development versions into a fresh
  conda environment or risk modifiying an existing working environment
  in unintended and/or undesireable ways with upgraded or downgraded
  dependencies.

  .. code-block:: bash

      conda create --name dev_env -c kutaslab/label/pre-release -c defaults -c conda-forge mkpy


Install from source (not recommended for general use)
-----------------------------------------------------

Clone the github repository into the current directory and pip install
the to the local source into the current environment's `site-packages`

.. code-block:: bash

   git clone https://github.com/kutaslab/mkpy
   cd mkpy
   pip install .


Install editable source code (development mode)
-----------------------------------------------

Python package installation ordinarily puts a frozen snapshot of the
package into the current environment's `site-packages`. If you want to
modify the mkpy source and have the changes show up when you import
the package and call the methods you install in "development mode" 
which puts a link to your souce code directory in "site-packages". 

.. code-block:: bash

   git clone https://github.com/kutaslab/mkpy
   cd mkpy
   pip install . -e


pip installation from PyPI
--------------------------

Not implemented. Install from source if you want the source; if you
need dependency management, use conda.


