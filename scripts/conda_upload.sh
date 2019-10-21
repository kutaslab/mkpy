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
#    export ANACONDA_TOKEN="an-actual-token"
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

# set parent of conda-bld, the else is only local user for testing in active conda env
if [ $USER = "travis" ]; then
    bld_prefix="/home/travis/miniconda"  # from the .travis.yml
else
    bld_prefix=${CONDA_PREFIX}
fi

# enforce some version number requirements before uploading to conda
tarball=`/bin/ls -1 ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*-*.tar.bz2`

# version is the package and conda meta.yaml {% version = any_stringr %}
version=`echo $tarball | sed -n "s/.*\(${PACKAGE_NAME}-.\+\)-.*/\1/p"`

# empty unless version is major.minor.patch
release=`echo $tarball | sed -n "s/.*\(${PACKAGE_NAME}-\([0-9]\+\.\)\{1,2\}[0-9]\+\)-.*/\1/p"`

# discourage casual misuse
if [ "$TRAVIS" != "true" ]; then
    echo "This script meant to run on TravisCI, see notes to run locally."
    exit -1
fi

# switch conda label, upload behavior and enforce versioning
if [ $TRAVIS_BRANCH = "master" ]; 
then
    # versioning: whitelist major.minor.patch on master branch
    if [[ "$version" != "$release" ]]; then
	echo "$PACKAGE_NAME development error: the github master branch version ${version} should be major.minor.patch"
	exit -2
    fi

    # do *NOT* force master onto main, we want conda upload to fail on
    # version collisions
    FORCE="" 
    conda_label="main"

else
    # versioning: blacklist major.minor.patch on non-master branches
    if [[ "$version" == "$release" ]]; then
	echo "$PACKAGE_NAME development error: development branch $TRAVIS_BRANCH is using a release version number: ${version}"
	exit -3
    fi
	
    # *DO* force non-master branches to overwrite existing labels so
    # we can test conda install from Anaconda Cloud with the latest
    # development version
    FORCE="--force" 
    conda_label=latest$TRAVIS_BRANCH
fi


# force convert even though compiled C extension ... whatever works cross-platform works
rm -f -r ./tmp-conda-builds
mkdir -p ./tmp-conda-builds/linux-64
cp ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*.tar.bz2 ./tmp-conda-builds/linux-64
# conda convert --platform all ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*.tar.bz2 --output-dir ./tmp-conda-builds --force
conda convert --platform linux-64 ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*.tar.bz2 --output-dir ./tmp-conda-builds --force
/bin/ls -l ./tmp-conda-builds/**/${PACKAGE_NAME}-*.tar.bz2


# so what have we here ...
echo "conda_upload.sh"
echo "travis branch: $TRAVIS_BRANCH"
echo "package name: $PACKAGE_NAME"
echo "conda-bld: ${bld_prefix}/conda-bld/linux-64"
echo "conda version: $version"
echo "release: $release"
echo "upload destination label: $conda_label"
echo "upload force flag: $FORCE"

echo "Deploying to Anaconda.org like so ..."
conda_cmd="anaconda --token $ANACONDA_TOKEN upload ./tmp-conda-builds/**/${PACKAGE_NAME}-*.tar.bz2 --label $conda_label --register ${FORCE}"
echo ${conda_cmd}

if ${conda_cmd};
then
    echo "Successfully deployed to Anaconda.org."
else
    echo "Error deploying to Anaconda.org"
    exit -4
fi
exit 0

