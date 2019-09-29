import os
import pprint as pp
from pathlib import Path
from .config import TEST_DIR, S01, CALSTEST_H5, MAKE_CALSTEST_H5, mkpy
from mkpy import mkh5
from mkpy.pygarv import PyYarf


def test_init():
    pyarf = PyYarf()
    return pyarf


def test_read_from_yaml():
    pyarf = test_init()
    yarf_f = TEST_DIR("data/calstest.yarf")
    yarf_docs = pyarf.read_from_yaml(yarf_f)
    pp.pprint(yarf_docs)


def test_read_from_mkh5():
    if not CALSTEST_H5.exists():
        MAKE_CALSTEST_H5()
    pyarf = test_init()
    pyarf.read_from_mkh5(CALSTEST_H5)
    os.remove(CALSTEST_H5)
    # pp.pprint(yarf_docs)


def test_to_yaml():
    if not CALSTEST_H5.exists():
        MAKE_CALSTEST_H5()
    pyarf = test_init()
    yarf_docs = pyarf.read_from_mkh5(CALSTEST_H5)
    pyarf.to_yaml(yarf_docs)
    os.remove(CALSTEST_H5)
    # pp.pprint(yarf_docs)


def test_pygarv_yaml_io():

    # pg = pygarv.PyGarv()
    # yaml_catalog = ''
    # for pgt in pg._catalog:
    #     yaml_catalog += pgt.specs_as_yaml
    # # pyarf.lint_yarf(yaml_catalog)

    # pyarf = pygarv.PyYarf('data/mne_three_subs.h5')
    # pdb.set_trace()

    # pyarf.set_test(2,0, {'here':'we', 'go': 27})
    # pdb.set_trace()
    # pyarf.new_yarf('data/mne_three_subs.yarf')
    # this_test = pyarf.get_test(0,0)
    # print()
    # print('# YAML CATALOG')
    # print(yaml_catalog)

    # from_yaml = [d for d in yaml.load_all(yaml_catalog)]
    # tests = list()
    # for t in from_yaml:
    #     test = list()
    #     for tt in t:
    #         test.append(tt)
    #     tests.append(test)
    # # pp.pprint(tests)

    # yaml_tests = ''
    # for t in tests:
    #     yaml_tests += yaml.dump(t,
    #                             explicit_start = True,
    #                             default_flow_style=False)
    # print(yaml_tests)
    # del(pg)
    pass
