"""cross various regexp patterns w/ event code sequences verify output

Event codes
   - length: 1-5
   - sign +/-

Event code array:
   # two parts: head, tail
   head lengths: 0, 1
   tail lengths: 0, 1, more than one
   - length: description
        0:  empty list, i.e., len(head) == len(tail) == 0
        1:  singleton list, i.e., len(head) == 1, len(tail) == 0
        2:  len(head) == len(tail) == 1
        3:  len(head) == 1, len(tail) > 1

Patterns:
   - capture groups
   - literals
      - \d
      - fancy crap (?*** )

"""


import pdb
from .config import TEST_DIR, IRB_DIR, GET_IRB_MKDIG, irb_data, mkpy
from mkpy import mkh5
from mkpy.mkh5 import CodeTagger as ct


# code lenght 1-6
def get_codes(length):
    return range(10 ** (length - 1), 10 ** length)


def codes_to_str(codes, sep):
    code_str = ""
    for c in codes:
        code_str += sep + str(c)
    return code_str


def anchor_gen(code_str, sep):
    anchor_patterns = [[], [], [], []]  # index == len(code), 0, 1, 2, ...
    codes = [code for code in code_str.split(sep) if len(code) > 0]
    maxlen = max([len(c) for c in codes])

    # len head always == 1, len tail varies 0 ... n
    for length in range(1, maxlen + 1):
        # case 1: len(tail) == 0 so head == tail
        if length == 1:
            anchor_patterns[1].append(r"(#\d)")
            anchor_patterns[1].append(r"(#\d{1})")
            anchor_patterns[1].append(r"(#\d{1,1})")
            for c in codes:
                if len(c) == length:
                    anchor_patterns[1].append(r"(#{0})".format(c))

        # case 2: len(tail) ==1 so head != tail
        if length == 2:
            # ways to match single digit w/ literal and
            anchor_patterns[2].append(r"(#\d\d)")
            anchor_patterns[2].append(r"(#\d{1}\d)")
            anchor_patterns[2].append(r"(#\d\d{1})")
            anchor_patterns[2].append(r"(#\d{1}\d{1})")
            anchor_patterns[2].append(r"(#\d{1}\d{1,1})")
            for c in codes:
                if len(c) == length:
                    anchor_patterns[2].append(r"(#{0})".format(c))
                    anchor_patterns[2].append(r"(#{0}\d)".format(c[0]))
                    anchor_patterns[2].append(r"(#\d{0})".format(c[1]))

        # case 3: len(tail) > 1
        if length == 3:
            # ways to match single digit w/ literal and
            anchor_patterns[3].append(r"(#\d\d\d)")
            anchor_patterns[3].append(r"(#\d{1}\d\d)")
            anchor_patterns[3].append(r"(#\d{1,1}\d\d)")

            anchor_patterns[3].append(r"(#\d\d{1}\d)")
            anchor_patterns[3].append(r"(#\d\d{1,1}\d)")

            anchor_patterns[3].append(r"(#\d\d\d{1})")
            anchor_patterns[3].append(r"(#\d\d\d{1,1})")

            anchor_patterns[3].append(r"(#\d{1}\d{1}\d)")
            anchor_patterns[3].append(r"(#\d{1}\d{1,1}\d)")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1}\d)")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1,1}\d)")

            anchor_patterns[3].append(r"(#\d{1}\d\d{1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d\d{1})")
            anchor_patterns[3].append(r"(#\d{1}\d\d{1,1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d\d{1,1})")

            anchor_patterns[3].append(r"(#\d{1}\d{1}\d{1})")
            anchor_patterns[3].append(r"(#\d{1}\d{1}\d{1,1})")
            anchor_patterns[3].append(r"(#\d{1}\d{1,1}\d{1})")
            anchor_patterns[3].append(r"(#\d{1}\d{1,1}\d{1,1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1}\d{1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1}\d{1,1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1,1}\d{1})")
            anchor_patterns[3].append(r"(#\d{1,1}\d{1,1}\d{1,1})")

            anchor_patterns[3].append(r"(#\d{2}\d)")
            anchor_patterns[3].append(r"(#\d{2,2}\d)")

            anchor_patterns[3].append(r"(#\d{3})")
            anchor_patterns[3].append(r"(#\d{3,3})")
            for c in codes:
                if len(c) == length:
                    anchor_patterns[3].append(r"(#{0})".format(c))
                    anchor_patterns[3].append(r"(#{0}\d\d)".format(c[0]))
                    anchor_patterns[3].append(r"(#\d{0}\d)".format(c[1]))
                    anchor_patterns[3].append(r"(#\d\d{0})".format(c[2]))
    return anchor_patterns


def test_code_lengths():
    max_code_len = 3
    test_codes = []
    for cl in range(1, max_code_len + 1):
        test_codes.extend([c for c in get_codes(cl)])
    sep = " "

    # test_codes = [1, 2, 3, 4, 5] + [11, 12, 13, 14, 15] + [101, 102, 103, 104, 105] #  + \
    # [1001, 1002, 1003, 1004, 1005] + \
    # [10001, 10002, 10003, 10004, 10005] + \
    # [20001, 20002, 20003, 20004, 20005] + \
    # [30001, 30002, 30003, 30004, 30005] + \
    # [40001, 40002, 40003, 40004, 40005] + \
    # [50001, 50002, 50003, 50004, 50005] + \
    # [60001, 60002, 60003, 60004, 60005]

    test_code_str = codes_to_str(test_codes, sep)
    ticks = [i for i in range(len(test_codes))]

    # print(test_code_str)
    anchor_patterns = anchor_gen(test_code_str, sep)
    other_patterns = [[], [], [], []]
    for i, ap in enumerate(anchor_patterns):
        other_patterns[i] = [p.replace("#", "") for p in ap]

    # print(anchor_patterns)
    # print(other_patterns)

    myct = ct(TEST_DIR("data/simple.ytbl"))
    # print(test_codes)
    for i, v in enumerate(anchor_patterns):
        for j, patt in enumerate(v):
            # print(patt)
            if j < len(v) - 1:
                other_patt = " " + other_patterns[i][j + 1]
            else:
                other_patt = ""
            p = patt + other_patt
            # print("pattern: {0}".format(p))
            res = myct._find_evcodes(p, ticks, test_codes)
            if res is None:
                # print("not found")
                continue
            for r in res:
                # print("\tresult: ", end=" ")
                for g in r:
                    # print("{0}".format(g[3][1]), end=" ")
                    if len(g[3][1]) != i:
                        raise RuntimeError(
                            "uh oh ... matched code has the wrong length"
                        )
                # print("")


@irb_data
def test_irb_special_cases():

    ytbl_f = TEST_DIR("data/codemap_test.ytbl")

    subid = "test2"
    h5f = IRB_DIR / "mkh5" / (subid + "_event_table.h5")

    myh5 = mkh5.mkh5(h5f)
    myh5.reset_all()
    myh5.create_mkdata(subid, *GET_IRB_MKDIG(subid))

    event_table = myh5.get_event_table(ytbl_f)
    # print(event_table.columns)

    cols_of_interest = [
        "dblock_path",
        "regexp",
        "log_evcodes",
        "anchor_code",
        "match_code",
    ]
    for test in [
        "neg_last",
        "neg_code",
        "neg_last_plus_one",
        "code_frag",
        "pos_last",
        "set_initial",
        "set_medial",
    ]:
        try:
            # print(event_table.loc[test, cols_of_interest])
            event_table.loc[test, cols_of_interest]
        except Exception:
            print("Index {0} not found in event_table".format(test))
