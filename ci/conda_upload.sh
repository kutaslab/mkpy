# Anaconda Cloud package uploader.
# 
# Runs but doesn't attempt the upload unless 
# 
#  * the package version from __init__.py and meta.yaml is {% version = "Major.Minor.Patch"}
# 
#  * the current build is on a branch named vMajor.Minor.Patch, which TravisCI believes it to
#    be when the build is triggered by a gihub release tagged as vMajor.Minor.Patch

# some guarding ...
if [[ -z ${CONDA_DEFAULT_ENV} ]]; then
    echo "activate a conda env before running conda_upload.sh"
    exit -1
fi

# intended for TravisCI deploy but can be tricked into running locally
if [[ "$TRAVIS" != "true" || -z "$TRAVIS_BRANCH" || -z "${PACKAGE_NAME}" ]]; then
    echo "conda_upload.sh is meant to run on TravisCI"
    exit -2
fi

# set parent of conda-bld or use $CONDA_PREFIX for local testing
# bld_prefix=${CONDA_PREFIX}
bld_prefix="/home/travis/miniconda"  # from the .travis.yml

# on travis there should be a single linux-64 package tarball. insist
tarball=`/bin/ls -1 ${bld_prefix}/conda-bld/linux-64/${PACKAGE_NAME}-*-*.tar.bz2`
n_tarballs=`echo "${tarball}" | wc -w`
if (( $n_tarballs != 1 )); then
    echo "found $n_tarballs package tarballs there must be exactly 1"
    echo "$tarball"
    exit -3
fi

# entire version string from __init__.py and the conda meta.yaml {% version = any_stringr %}
version=`echo $tarball | sed -n "s/.*${PACKAGE_NAME}-\(.\+\)-.*/\1/p"`

# just the numeric major.minor.patch portion of version, possibly empty
mmp=`echo $version | sed -n "s/\(\([0-9]\+\.\)\{1,2\}[0-9]\+\).*/\1/p"`

# Are we refreshing master or building a release version according to
# the convention that releases are tagged vMajor.Minor.Release?
#
# * if $version = $mmp then version is a strict numeric
#   Major.Minor.Patch, not further decorated, e.g., with .dev this or
#   rc that
# 
# * the github release tag, e.g., v0.0.0 shows up in the Travis build
#   as the branch name so $TRAVIS_BRANCH = v$mmp enforces the
#   vMajor.Minor.Patch release tag convention for conda upload to main

# assume this is a dry run unless TRAVIS_BRANCH informs otherwise
# deviations from M.N.P versions are always dry-runs, e.g., M.N.P.dev1

label="dry-run"
#if [[ "${version}" = "$mmp" ]]; then
if [[ "${version}" =~ ^${mmp}(.dev[0-9]+){0,1}$ ]]; then

    # commit to dev uploads to /pre-release
    if [[ $TRAVIS_BRANCH = "dev" ]]; then
	label="pre-release"
    fi

    # a github release tagged vM.N.P uploads to /main
    if [[ $TRAVIS_BRANCH = v"$mmp" ]]; then
	label="main"
    fi
fi

# build for multiple platforms ... who knows it might work
mkdir -p ${bld_prefix}/conda-convert/linux-64
cp ${tarball} ${bld_prefix}/conda-convert/linux-64
cd ${bld_prefix}/conda-convert
conda convert -p linux-64 -p osx-64 -p win-64  linux-64/${PACKAGE_NAME}*tar.bz2

# POSIX trick sets $ANACONDA_TOKEN if unset or empty string 
ANACONDA_TOKEN=${ANACONDA_TOKEN:-[not_set]}
conda_cmd="anaconda --token $ANACONDA_TOKEN upload ./**/${PACKAGE_NAME}*.tar.bz2 --label ${label} --skip-existing"

# thus far ...
echo "conda meta.yaml version: $version"
echo "package name: $PACKAGE_NAME"
echo "conda-bld: ${bld_prefix}/conda-bld/linux-64"
echo "tarball: $tarball"
echo "travis tag: $TRAVIS_TAG"
echo "travis branch: $TRAVIS_BRANCH"
echo "conda label: ${label}"
echo "conda upload command: ${conda_cmd}"
echo "platforms:"
echo "$(ls ./**/${PACKAGE_NAME}*.tar.bz2)"

# if the token is in the ENV and this is a release/tagged commit or equivalent
#    attempt the upload 
# else
#    skip the upload and exit happy
if [[ $ANACONDA_TOKEN != "[not_set]" && ( $label = "main" || $label = "pre-release" ) ]]; then

    conda install anaconda-client

    echo "uploading to Anconda Cloud: $PACKAGE_NAME$ $version ..."
    if ${conda_cmd}; then
    	echo "OK"
    else
    	echo "Failed"
    	exit -5
    fi
else
    echo "$PACKAGE_NAME $TRAVIS_BRANCH $version conda_upload.sh dry run ... OK"
fi
exit 0
