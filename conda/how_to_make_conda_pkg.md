In active conda environemnt `active_env` or whatever, from parent directory to this one, and replace X.Y.Z with actual version 

    conda-build purge
    conda-build -c defaults -c kutaslab conda
    mkdir -p conda_build/linux-64
    cd conda_build
    cp  -r ~/.conda/envs/active_env/conda-bld/linux-64 .
    conda convert --platform all linux-64/mkpy-.X.Y.Z.actual_file_name.tar.bz2
    anaconda login
    anaconda upload -i -u kutaslab ./**/mkpy*X.Y.Z*.tar.bz2
    anaconda logout
