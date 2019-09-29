Installation
============

A copy of the ``mkpy`` package is cloned from the Kutas Lab local
``git`` repository at ``/mnt/cube/mkgit`` and installed with ``pip``.

.. Note:: `mkpy` is restricted to python 3.6 until other packages support 3.7


Adding `mkpy` to an existing `conda` enviroment 
------------------------------------------------

To install `mkpy` in an existing python 3.6 conda environment at the
terminal command line 
are found. 


1. In a ``bash`` shell terminal, navigate to some scratch or
   temp directory and activate the ``conda`` enviroment.

.. code-block:: bash

   conda activate my_env

2. Clone the ``mkpy`` git repository into the current directory.

.. code-block:: bash

   git clone /mkgit/mkpy .

4. Navigate to the `./mkpy` directory where the `setup.py` and
   `requirements.txt` files are found and install the dependencies and
   mkpy like so:

.. code-block:: bash

   cd mkpy
   pip install -r requirements.txt
   pip install .


Creating a new `conda` conda enviroment for  `mkpy`
---------------------------------------------------

1. Run this with a sensible name in place of `some_env` and then
follow the steps above.

.. code-block:: bash

    create conda -n some_env python=3.6 pip


2. Follow the steps above for adding `mkpy` to an existing `conda`
   enviroment.

