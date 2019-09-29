import yaml
import json
import pdb
import pprint
import pandas as pd
import io
import glob
import os.path
import json
import dpath.path
import dpath.util


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
                slash_keys_only = [
                    "/".join([str(s) for s in sp]) for sp in keys_only
                ]
                keys_vals = [
                    dpath.path.paths_only([k for k in p])
                    for p in dpath.path.paths(hdr, leaves=True)
                ]  # , path=[mykeys])]
                slash_keys_vals = [
                    "/".join([str(s) for s in sp]) for sp in keys_vals
                ]

                # hdr_data = []
                # for k,v in attr_fetcher.items():
                #     hdr_data.append((k, dpath.util.get(hdr, v)))
                # # print(hdr_data)
                # hdr_df = pd.DataFrame.from_items(hdr_data)
                # print(hdr_df)

            # ymood = dpath.util.get(hdr, 'runsheet/mood_induction')
            # print(ymood)
            # mood = pd.DataFrame(ymood)
            # print(mood)

            # json_str = json.dumps(hdr)
            # mykeys = ['topkey']

            # keys_only = [dpath.path.paths_only([k for k in p]) \
            #               for p in dpath.path.paths(hdr, leaves=False, path=[mykeys])]
            # slash_keys_only = ['/'.join([str(s) for s in sp]) for sp in keys_only]
            # slash_keys_vals = list(set(slash_keys_vals) - set(slash_keys_only))
            # slash_keys_vals.sort()
            # print(slash_keys_vals)
            # pdb.set_trace()

            # print()
            # for d in docs:
            #     for k in d.keys():
            #         if 'mood_induction' in k:
            #             print(k)
            #             print(d[k])
            #             print(json.dumps(d[k], allow_nan=False))
            #             if k in ['streams',  'sensors']:
            #                 pass
            #         # df = pd.read_csv(io.StringIO(d[k]),
            #         #                  index_col=0,
            #         #                  delim_whitespace=True)
            #         # df_dict = df.to_dict('index')
            #         # pprint.pprint(df_dict)

            # # keys = ['neuropsych', 'age', 'notes',
            # #     'mood_induction_map',
            # #     'mood_induction_list',
            # #     'mood_induction_table', ]
            # # keys = ['description', 'notes']
            # # print()
            # # for k in keys:
            # #     if k in d.keys():
            #         print(d[k])
        except Exception as fail:
            msg = "uh oh ... trouble with " + yhdr_f
            raise fail(msg)
