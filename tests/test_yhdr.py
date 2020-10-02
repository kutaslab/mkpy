import yaml
import json
import pdb
import pprint
import pandas as pd
import io
import glob
import os.path
import json

# import dpath.path
# import dpath.util
from mkpy import dpath


def test_load():
    runsheet = dict()
    test_files = glob.glob(os.path.join("data/", "SNN.yhdr"))
    test_files = [f for f in test_files if "bad" not in f]
    for yhdr_f in test_files:
        try:
            with open(yhdr_f, "r") as f:

                print()
                docs = yaml.load_all(f.read())
                hdr = dict()
                for d in docs:
                    hdr[d["name"]] = d

                streams = dpath.util.get(hdr, "apparatus/streams")
                streams = pd.DataFrame.from_dict(streams, orient="index")
                print(streams)

                fiducials = dpath.util.get(hdr, "apparatus/fiducials")
                fiducials = pd.DataFrame.from_dict(fiducials, orient="index")
                print(fiducials)

                sensors = dpath.util.get(hdr, "apparatus/sensors")
                sensors = pd.DataFrame.from_dict(sensors, orient="index")
                print(sensors)

                keys_only = [
                    dpath.path.paths_only([k for k in p])
                    for p in dpath.path.paths(hdr, leaves=False)
                ]
                slash_keys_only = ["/".join([str(s) for s in sp]) for sp in keys_only]
                keys_vals = [
                    dpath.path.paths_only([k for k in p])
                    for p in dpath.path.paths(hdr, leaves=True)
                ]  # , path=[mykeys])]
                slash_keys_vals = ["/".join([str(s) for s in sp]) for sp in keys_vals]

        except Exception as fail:
            msg = "uh oh ... trouble with " + yhdr_f
            raise fail(msg)
