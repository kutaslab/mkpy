Release Notes
=============


v0.1.6 
------

Minor patch to include nose in mkpy requirements so the mkpy/dpath
tests run with conda package installation.


v0.1.5 
------

Release notes begin with version 0.1.5, the initial `mkpy`
release on github and corresponding conda package on the kutaslab
Anaconda Cloud channel.


Brief History
-------------

In 2017-2018 ``mkpy`` was developed and git version controlled up
through version 0.1.4 on Kutas Lab servers only. The data files for
the pytests were a mix of IRB protected human subjects EEG research
data and other test data.

In 2018, ``mkpy_public``, a static snapshot of the source and docs
were uploaded to github/kutaslab/mkpy_public without any test data.

In Fall 2019, the test data files were segregated, with IRB protected
data moved out of the mkpy repo subdirectories and the repo rebuilt
without human subjects research data in any form. This allows mkpy
source, docs, and test files to be hosted on a public github repo. The
pytests were modified to skip tests on the privacy protected data
without failing when the files are not found.  Consequently the full
test suite runs on the Kutas Lab development server while mkpy
installed via the conda or pypi packages or from the source on github
can still run a working subset of tests to smoke test the
installation.

