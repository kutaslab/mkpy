%clear all;
h5file =   '/home/turbach/TPU_Projects/mkpy/mkpy/tests/data/test_create_expt.h5';
info = h5info(h5file);
att = info.Groups(1).Groups(1).Datasets.Attributes.Value;
jst = loadjson(att{1});
