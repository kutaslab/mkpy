# Notes: mkpy
#   turbach 10/20/19
#
#
# * Bash script for use with a github repo and a .travis.yml deploy
#   script provider, example below. Requires several environment
#   variables (in caps) including a current $ANACONDA_TOKEN for the
#   destination channel.
#
# * This does a little git branch switching so master branch is uploaded
#   to conda with the label "main" and non-master branches are
#   uploaded with label "latest${TRAVIS_BRANCH} and clobber previous
#   uploads on that branch. This is for round-trip develop, test,
#   upload-to-conda, install-from-conda, test cycle. See Anaconda
#   Cloud docs for more on labels.
#
# * The package version that automagically appears on conda comes from the
#   conda meta.yaml variable
# 
#     {% version = "..." %} 
#
#   embedded in the conda-build output tar.bz2 + the git commit short
#   hash NOT the git branch name.
# 
# * For local testing in an active conda env, fake the TravisCI env
#   like so and make sure there is a unique package tar.bz2 in the
#   relevant conda-bld dir before converting.
#
#    export TRAVIS="true"
#    export TRAVIS_BRANCH="X.Y.Z" 
#    export PACKAGE_NAME="an-actual-name"
#
#  * Example .travis.yml for a linux-64 package
# 
#    # BEGIN .travis.yml ----------------------------------------
#    # spudtr requires a current GIT_TOKEN and ANACONDA_TOKEN on TravisCI kutaslab/spudtr
#    env:
#        - PACKAGE_NAME: spudtr   # for the conda_upload.sh deploy script
#    language: minimal
#    before_install:
#        - wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
#        - bash miniconda.sh -b -p $HOME/miniconda
#        - export PATH="$HOME/miniconda/bin:$PATH"
#        - hash -r
#        - conda config --set always_yes yes --set changeps1 no
#        - conda info -a
#        - conda install conda-build conda-verify
#    install:
#        - conda build conda -c defaults -c conda-forge
#        - conda create --name spudtr_env spudtr -c local -c defaults -c conda-forge
#        - source activate spudtr_env  # so tests run in env as installed by conda
#        - conda install black pytest-cov
#        - conda list
#        - lscpu
#        - python -c 'import numpy; numpy.show_config()'
#    script:
#        - black --check --verbose --line-length=79 .
#        - pytest --cov=spudtr
#    after_success:
#        - pip install codecov && codecov
#    before_deploy:
#        - pip install sphinx sphinx_rtd_theme jupyter nbsphinx nbconvert!=5.4
#        - conda install -c conda-forge pandoc
#        - conda install anaconda-client
#        - conda list
#        - sphinx-apidoc -e -f -o docs/source . ./tests/* ./setup.py
#        - make -C docs html
#        - touch docs/build/html/.nojekyll
#    deploy:
#        # convert and upload to Anaconda Cloud. Script routes uploads like so
#        #  * master branch goes to --channel somechan/spudtr/main
#        #  * other branches go to --channel somechan/spudtr/latest$TRAVIS_BRANCH
#        - provider: script
#          skip_cleanup: true
#          script: bash ./scripts/conda_upload.sh
#          on:
#              all_branches: true
#   
#        # only master branch refreshes the docs
#        - provider: pages
#          skip_cleanup: true
#          github_token: $GITHUB_TOKEN
#          on:
#              branch: master
#          target_branch: gh-pages  # that's the default anyway, just to be explicit
#          local_dir: docs/build/html
# # END .travis.yml ----------------------------------------

# POSIX magic sets an unset or empty $ANACONDA_TOKEN to the default string "[none]"
ANACONDA_TOKEN=${ANACONDA_TOKEN:-[not_set]}
if [[ ${ANACONDA_TOKEN} = "[not_set]" ]]; then
    echo 'TravisCI $ANACONDA_TOKEN is not set, this dry run will run not attempt the upload.'
fi

# some guarding ...
if [[ -z ${CONDA_DEFAULT_ENV} ]]; then
    echo "activate a conda env before running conda_upload.sh"
    exit -1
fi

# discourage casual misuse
if [[ "$TRAVIS" != "true" || -z "$TRAVIS_BRANCH" || -z "${PACKAGE_NAME}" ]]; then
    echo "conda_upload.sh is meant to run on TravisCI, see notes to run locally."
    exit -2
fi

# set parent of conda-bld, the else isn't needed for travis, simplifies local testing
if [ $USER = "travis" ]; then
    bldgq_prefix="/home/travis/miniconda"  # from the .travis.yml
else
    bld_prefix=${CONDA_PREFIX}
fi

# on travis there should be a single linux-64 package tarball. insist
tarball=`/bin/ls -1 ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*-*.tar.bz2`
n_tarballs=`echo "${tarball}" | wc -w`
if (( $n_tarballs != 1 )); then
    echo "found $n_tarballs package tarballs there must be exactly 1"
    echo "$tarball"
    exit -3
fi

# tarball="whatever/mkpy-v0.12.2.dev0-blahblah.tar.bz2"

# version is the package and conda meta.yaml {% version = any_stringr %}
version=`echo $tarball | sed -n "s/.*${PACKAGE_NAME}-[v]\{0,1\}\(.\+\)-.*/\1/p"`

# extract the major.minor.patch of version
mmp=`echo $version | sed -n "s/\(\([0-9]\+\.\)\{1,2\}[0-9]\+\).*/\1/p"`

# toggle whether this is a release version
if [[ "${version}" = "$mmp" ]]; then
    release="true"
else
    release="false"
fi

# switch conda label, upload behavior and enforce versioning
if [ $TRAVIS_BRANCH = "master" ];
then
    # versioning: whitelist major.minor.patch on master branch
    if [[ $release != "true" ]]; then
	echo "$PACKAGE_NAME development error: the github master branch version ${version} should be major.minor.patch"
	exit -4
    fi

    # do *NOT* force master onto main, we want conda upload to fail on
    # version collisions
    FORCE="" 
    conda_label="main"

else
    # versioning: blacklist major.minor.patch on non-master branches
    if [[ "$version" == "$release" ]]; then
	echo "$PACKAGE_NAME development error: development branch $TRAVIS_BRANCH is using a release version number: ${version}"
	exit -5
    fi
	
    # *DO* force non-master branches to overwrite existing labels so
    # we can test conda install from Anaconda Cloud with the latest
    # development version
    FORCE="--force" 
    conda_label=latest_br$TRAVIS_BRANCH
fi

# mkpy doesn't convert, compiled C extension
# rm -f -r ./tmp-conda-builds
# mkdir -p ./tmp-conda-builds/linux-64
# cp $tarball ./tmp-conda-builds/linux-64
# conda convert --platform linux-64 ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*.tar.bz2 --output-dir ./tmp-conda-builds --force
# /bin/ls -l ./tmp-conda-builds/**/${PACKAGE_NAME}-*.tar.bz2

# so what have we here ...
echo "conda_upload.sh"
echo "travis branch: $TRAVIS_BRANCH"
echo "package name: $PACKAGE_NAME"
echo "conda-bld: ${bld_prefix}/conda-bld/linux-64"
echo "conda version: $version"
echo "release: $release"
echo "upload destination label: $conda_label"
echo "upload force flag: $FORCE"
echo "Anaconda.org upload command ..."
conda_cmd="anaconda --token $ANACONDA_TOKEN upload ${tarball} --label $conda_label --register ${FORCE}"
echo "conda upload command: ${conda_cmd}"

if [[ $ANACONDA_TOKEN = "[not_set]" ]]; then
    echo "${PACKAGE_NAME}" 'dry run OK ... set ANACONDA_TOKEN on TravisCI to upload this version to Anaconda Cloud'
    exit 0
fi

# upload for real ...
if ${conda_cmd};
then
    echo "Successfully deployed to Anaconda.org."
else
    echo "Error deploying to Anaconda.org"
    exit -6
fi
exit 0

