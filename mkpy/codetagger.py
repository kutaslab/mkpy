import re
import yaml
import numpy as np
import pandas as pd
import warnings


class CodeTagger:
    """Tag pattern-matched sequences of time-indexed integer with key:value metadata.

    In the intended use case

    * the integer values are event-markers recorded on an event or
      timing track of a digital data acquisition system.

    * Each integer maps to a specific event or event-type, e.g., a
      stimulus onset/offset, a response, a timing mark.

    * A sequence of integers corresponds to a sequence of events or
      event types.

    * The metadata (tabular rows x columns) add further information
      above and beyond the numeric value of the integer and may
      include are mapped to tuples of mixed data types: strings,
      integers, floats, suitable for decorating events and epochs of
      data with useful information such experimental design factor
      levels (Easy, Hard), continuous covariates (age of acquisition).

    The original use case was to find and decorate ERPSS log event
    codes with experimental information.

    The mechanism here is general, abstracting away from the source of
    the integer 1-D arrays and the intended purpose of the metadata.

    Usage
    -----

    The UI for specifying a code tag map can be any of these file types

     Excel
       an .xlsx file and (optional) named worksheet readable by
       pandas.DataFrame.read_excel()

       CodeTagger('myexpt/code_tag_table.xlsx')
       CodeTagger('myexpt/code_tag_table.xlsx!for_evoked')
       CodeTagger('myexpt/code_tag_table.xlsx!for_mixed_effects')

     Tabbed text 
        a rows x columns tab-delimited text file readable by
        pandas.Data.read_csv(..., sep="\t").

     YAML
        a yaml map readable by yaml.load(), mock-tabular format
        described below.


    * File formats

        Excel and Tabbed-text
            1. the data must be tabular in n rows and m columns (i,j >= 2)
            2. column labels must be in the first row
            3. the column labels must include 'regexp'
            4. there must be at least one tag column, there may be more

	    +------------+--------------+------------------+
            | regexp     | col_label_1  |  <col_label_m>*  |
	    +============+==============+==================+
            | pattern_1  | code_tag_11  | <code_tag_1m>*   |
	    +------------+--------------+------------------+
            |  ...       |  ...         | ...              |
	    +------------+--------------+------------------+
            | pattern_n  | code_tag_n1  |  <datum_nm>*     |
	    +------------+--------------+------------------+
    
        YAML files
            The YAML can be any combination of inline (JSON-ic) and
            YAML indentation that PyYAML yaml.load can handle.

            1. must have one YAML document with two keys: ``columns`` and ``rows``.
            2. the first two column items must be `Index` and `regexp`.
            3. the columns may continue ad lib.
            4. each row must be a YAML sequence with the same number of items as there are columns



        Example

        .. code-block:: yaml

           ---
           'columns':
             [regexp, bin, probability, frequency, source]
           'rows':
             - ['(#1)', 1, hi,   880, oboe]
             - ['(#2)', 2, hi,   440, oboe]
             - ['(#3)', 3, lo,   880, oboe]
             - ['(#4)', 4, lo,   440, oboe]
             - ['(#5)', 5, hi,   880, tuba]
             - ['(#6)', 6, hi,   440, tuba]
             - ['(#7)', 7, lo,   880, tuba]
             - ['(#8)', 8, lo,   440, tuba]

    Row value data types

    regexp : regular expresion `pattern* (#pattern) pattern*`
        This is the code sequence search pattern.  Log codes are separated
        by a single whitespace for matching. The ``regexp`` has one or
        more time-locking pattern capture groups of which one begins
        with the time-marking anchor symbol, ``#``.

        Flanking code patterns may be capture groups (...) and
        non-capture groups (?:...)

        All matched time-locking codes, the anchor code, and distance
        between them are extracted from the mkpy.mkh5 datablocks and
        merged with the code tags in the returned event_table for all
        capture groups.
            
    Additional columns: scalar (string, float, int, bool)

    That's it. All the real work is done by 1) specifying regular
    expressions that match useful (sequences of) integer event codes
    and 2) specifying the optional column values that label the
    matched codes in useful ways, e.g., by specifying factors and
    levels of experimental design, or numeric values for regression
    modeling or ...

    Notes

    * The values in any given column should all be the same data type:
      string, integer, boolean, float. This is not enforced, violate
      at your own risk.

    * Missing data are allowed as values but discouraged b.c. 1) they
      are handled differently by the pandas csv reader vs. yaml and
      Excel readers. 2) the resulting NaNs and None coerce np.int and
      np.str dtype columns into np.object dtype and incur a
      performance penalty and 3) np.object dtypes are not readily
      serialized to hdf5 ... h5py gags and pytables pickles them. 4)
      It may lead to other unknown pathologies.

    * For yaml files, if missing values are unavoidable, coding them
      with the yaml value .NAN is recommended for all cases ... yes,
      even string data. The yaml value null maps to None and behaves
      differently in python/numpy/pandas. This is not enforced,
      violate at your own risk

    * Floating point precision. Reading code tag maps from yaml text files
      and directly from Excel .xlsx files introduces the same rounding
      errors for floating point numbers, e.g. 0.357 ->
      0.35699999999999998. Reading text files introduces a *different*
      rounding error, e.g.,0.35700000000000004.

    * There is no provision for <t:n-m> time interval constraints on
      code patterns. Maybe someday.

    """

    class MissingAnchor(Exception):
        def __init__(self, cause):
            msg = (
                "\nError: missing anchor mark\n"
                "Cause: {0}\n"
                "Fix: Mark exactly one target code pattern"
                "with a #  like this: (#mycode)\n"
            ).format(cause)
            print(msg)

    class MultipleAnchors(Exception):
        def __init__(self, cause):
            print("\nError: multiple anchor marks")
            print("Cause: {0}".format(cause))
            print(
                "Fix: Mark exactly one target code pattern with a #  like this: (#mycode)\n"
            )

    class BadCodePattern(Exception):
        def __init__(self, in_patt, cause=None):
            print(
                "\nError: Regular expression syntax error in code pattern: {0}".format(
                    in_patt
                )
            )
            if cause is not None:
                print("Cause: {0}".format(cause))

    def __init__(self, cmf):
        """initialize instance with a code tag map file. """

        # TODO: handle different filetypes, don't let things fail silently
        self.cmf = str(cmf)  # for Path

        loaders = {
            "xlsx": self._load_xlsx_map,
            "yaml": self._load_yaml_map,
            "text": self._load_txt_map,
        }

        fails = []
        code_map = None
        for kind, loader in loaders.items():
            try:
                code_map = loader(self.cmf)
            except Exception as fail:
                fails.append((kind, fail))
                continue

            # break out on success
            if code_map is not None:
                self.code_map = code_map
                return

        # uh oh ...
        for fail in fails:
            print(f"failed {fail[0]}: {fail[1]}")
        raise IOError(
            f"failed to load {cmf} as an xlsx, YAML, or text code map"
        )

        self._check_mapper(self.code_map)

    def _check_mapper(self, mapper):

        if not "regexp" in mapper.columns:
            raise Exception(f"codemap {self.cmf} must include a regexp column")

        if len(mapper.columns) < 2:
            raise Exception(
                f"codemap {self.cmf} must have regexp and "
                "at least one additional code tag column."
            )

        for row, pattern in enumerate(mapper["regexp"]):
            try:
                re.compile(pattern)
            except Exception as fail:
                print(f"regexp row {row}")
                raise fail

        if code_map.columns[0] == "Index":
            warnings.DeprecationWarning(
                "As of mkpy 0.2.1 codemaps no longer require an Index as the first column."
            )

    def _load_xlsx_map(self, cmf):
        """wraps pandas.Dataframe.read_excel() to load a code tag table from .xlsx

        Parameter
        ---------
            cmf : str or Path
                is path_to_file.xlsx[!named_sheet )path to an .xlsx file with optional.
                Default selects first worksheet use .xlsx!sheet_name syntax to select a
                named sheet.

        Returns
        -------
            mapper : pandas.Dataframe

        Examples
        --------
            _load_xlsx_map('myexpt/code_tag_table.xlsx')
            _load_xlsx_map('myexpt/code_tag_table.xlsx!for_evoked')
            _load_xlsx_map('myexpt/code_tag_table.xlsx!for_mixed_effects')

        """
        # use !named_sheet if there is one, else default to 0 == first
        cmf_reob = re.match(
            r"(?P<xl_f>.+\.xls[xm])[\!]*(?P<sheet_name>.*)$", cmf
        )
        xl_f = cmf_reob["xl_f"]
        sheet_name = cmf_reob["sheet_name"]
        if len(sheet_name) == 0:
            sheet_name = 0

        mapper = pd.read_excel(
            xl_f, sheet_name=sheet_name, header=0  # , index_col="Index"
        )
        return mapper

    def _load_txt_map(self, cmf):
        """load tab-separated UTF-8 text file and return pandas DataFrame"""
        with open(cmf, "r") as d:
            mapper = pd.read_table(
                cmf,
                delimiter="\t",
                header=0,
                encoding="utf-8",
                # index_col="Index",
            )
        return mapper

    def _load_yaml_map(self, cmf):
        """load yaml mapper file and return pandas DataFrame"""

        # slurp the code tags
        with open(cmf, "r") as d:
            mapper = yaml.load(d.read(), Loader=yaml.SafeLoader)

        # modicum of format checking ...
        if not isinstance(mapper, dict):
            msg = (
                "code tag map file is not a yaml map: "
                + "yaml.load({0}).__class__ == {1}".format(
                    self.cmf, mapper.__class__
                )
            )
            raise ValueError(msg)

        # nab column labels ... equivalent to header row in tabular code tag map
        try:
            col_labels = mapper["columns"]
            ncols = len(col_labels)
        except Exception:
            print('code tag map must have "columns" entry')
            raise

        # nab rows
        try:
            rows = mapper["rows"]
            nrows = len(rows)
        except Exception:
            print('code tag map must have "rows" entry')
            raise

        # modicum of value checking
        for mapvals in rows:
            # insist on non-empty column values
            if not (isinstance(mapvals, list) and len(mapvals) == ncols):
                msg = "{0}".format(mapvals)
                msg += " map values must be a list of {0} items: {1}".format(
                    ncols, col_labels
                )
                raise ValueError(msg)

            # check that the patterns will compile as a regexp
            re.compile(mapvals[mapper["columns"].index("regexp")])

        # return as a pandas data frame, indexed on Index
        mapper = pd.DataFrame(mapper["rows"], columns=mapper["columns"])
        # mapper.set_index("Index", inplace=True)
        return mapper

    def _pattern_to_str(self, pattern):
        """
        normalize different input data types to a string rep for re matching
        """
        # np.bytes_ has __abs__ so check it first ... yuck
        if isinstance(pattern, np.bytes_):
            # bytes
            patt_str = pattern.decode("utf8")
        elif hasattr(pattern, "__abs__"):
            # numeric ... +/-
            patt_str = pattern.__str__()
        elif isinstance(pattern, str):
            # strings
            patt_str = pattern
        else:
            msg = (
                "cannot convert {0} to string for pattern matching "
                "must be integer, bytes, or string"
            ).format(pattern)
            raise ValueError(msg)

        # try to be helpful about invisible characters
        if re.search(r"\\t", patt_str):
            msg = (
                "tab character in {0} never match, use a single "
                "white space to delimit event codes"
            ).format(patt_str)
            raise ValueError(msg)
        if re.search(r"\s{2,}", patt_str):
            msg = (
                "consecutive whitespaces in {0} never match, use a single "
                "white space to delimit event codes"
            ).format(patt_str)
            raise ValueError(msg)
        if re.match(r"^ ", patt_str):
            warnings.warn("leading whitespace in {0}".format(patt_str))
        if re.match(r" $", patt_str):
            warnings.warn("trailing whitespace in {0}".format(patt_str))

        # check regular expression syntax
        try:
            re.compile(pattern)
        except Exception as msg:
            raise self.BadCodePattern(in_patt=pattern, cause=msg)
        return patt_str

    def _parse_patt(self, pattern):
        """locate position of the anchor code in search pattern plus basic r.e. validation

        Parameters
        ----------
            pattern : regular expression string
                regular expression pattern with exactly one anchor capture group
                of the form (#...), optionally flanked by other code patterns

        Returns
        -------
            (anchor, capture_groups, code_patt) : tuple 
                anchor : tuple
                    (anchor_group_index, anchor_match_object)
                capture_groups : list
                    a list of the capture groups in pattern
                code_patt : regular expression string
                    regular expression pattern with the (one and only)
                    anchor marker # stripped

        """

        in_patt = self._pattern_to_str(
            pattern
        )  # coerce input to a sensible r.e.

        # define capture groups, supressing greedy matching w/ ? is essential
        capt_group_patt = (
            r"\((?!\?\:).+?\)"  # any ( ) except non-capturing (?: )
        )

        # anchor_patt = r'\(#[-]{0,1}\d+\)' # matches integer code literals only
        anchor_patt = (
            r"\(#.+\)"  # allow anchor pattern (# ...)  allows patterns
        )

        # look up the capture groups including anchors
        capture_groups = [g for g in re.finditer(capt_group_patt, in_patt)]

        # check exactly one anchor group
        anchors = [
            (i, g)
            for i, g in enumerate(capture_groups)
            if re.match(anchor_patt, g.group(0))
        ]
        if len(anchors) < 1:
            raise (self.MissingAnchor(pattern))
        elif len(anchors) > 1:
            raise (self.MultipleAnchors(pattern))
        else:
            anchor = anchors[0]

        # strip the # anchor mark
        # code_patt = re.sub(r'#', r'', in_patt)
        # like so to prevent stripping comments (?# ...)
        code_patt = re.sub(r"\(#", r"(", in_patt)

        # right-bound the captured group, e.g., (#10) -> (#10\b) else (#10) matches
        # and extracts 1024. No expressive loss b.c. (#1024) and (#10\d\d) also match 1024
        # The \b matches boundary at next white space or end of string
        code_patt = re.sub("\\)", "\\\\b)", code_patt)

        # these are used for pattern matching and lookup in find_codes
        return (anchor, capture_groups, code_patt)

    def _find_evcodes(self, pattern, ticks, evcodes):
        r"""Pattern match sequences of integer codes and extract timing information

        This finds arbitrary subsequences of integers in a 1-D array
        of integers (``evcodes``) and returns bundles of match and
        index information.

        Whereas individual integers are readily matched by numerical
        identity comparison, matching arbitrary subsequences requires
        a more general search algorithm. 

        Regular expression pattern matching over character strings
        affords just such generality, but based on character rather
        than numeric identity comparisons, i.e., 2/4 == 2 is true but
        '2/4' == '2' is false. So the 1-D integer array is mapped to
        1-D character array (=string) representation drawn from the
        alphabet ' -0123456789' with ' ' as a delimiter. Since the nth
        delimiter corresponds to 0-base index of the nth integer in
        the original array, the string positions of pattern matches on
        the string representation can be converted back to the indices
        of the corresponding values in the integer array.

        For the intended use case where integer correspond to event
        codes in a data stream it is convenient to single out one code
        as the "anchor" in the sequence, ``#...`` and to use the
        regular expression capture group mechanism ``( ... )`` to
        identify those portions of the sequence to extract and return:
        the anchor (#...) always and optionally other codes in the
        matching sequence.

        In conjunction with a specification of indexes into a data
        stream (``ticks``), each match bundle provides all the
        information necessary to look-up the location of the
        subsequence of integers in the original data stream.

        Approach: two steps

          1. preprocess the search pattern to find the # anchor mark and
             count the capture groups

          2. sweep the pattern across a string-ified representation of
             the integer event codes, extracting information bundles
             for each captured group: the obligatory anchor code always,
             and any other captured evcodes.

        The extracted information bundles are dictionaries that
        contain (primarily) the matched code in the `evcodes` vector,
        the matched tick in the `ticks`, the index i at which these
        values are found, i.e., idx such that evcodes[idx] = is the
        matching and ticks[idx] = the value of the tick at that
        match. Additional information specifies the relation between
        the match and the anchor pattern.

        Code Pattern Matching Definitions
        --------------------
        ``digits``: char
            The characters 0, 1, 2, 3, 4, 5, 6, 7, 8, 9. Each is
            matched by r'[0-9]' or equivalent, e.g., r'\d'

        ``code`` : str
            a sequence of one or more digits optionally preceded
            by the - character.  Matched by r'[-]{0,1}\d+'

        ``code pattern`` : regexp str
            any regular expression that matches a code. Such as r'1'
            to match code 1 or r'\d{2}' to match any two digit code or
            r'\d{3}1' to match any four digit code ending in 1 or
            r'\d{3}[02468]' to match any even four digit code.

        ``capturing code pattern`` : regexp str
           any code pattern of the form r'(...)' that matches a code
           or code sequence

        ``anchor pattern`` : regexp str
            any capturing code pattern that captures a subset of the codes
            captured by r'(#[-]{0,1}\d+)'.

        ``code sequence`` : str
            a sequence of codes, each preceded by a single a single whitespace.
            r'( [-]{0,1}\d+)+'

        ``search pattern`` : regexp str
            any regular expression that contains exactly one anchor
            pattern and matches a code or code sequence

            .. Note::
               A ``search pattern`` may contain capturing code
               patterns in addition to the anchor pattern
        """

        rvals = []  # return this

        # bail out if there's nothing to do
        if len(evcodes) == 0:
            warnings.warn("list of event codes is empty")
            return rvals

        # parse the pattern parameter into useful chunks.
        # details in _parse_patt().__doc__
        anchor, capture_groups, code_patt = self._parse_patt(pattern)
        try:
            patt_regx = re.compile(code_patt)
        except:
            msg = "cannot compile {0} as regular expression".format(code_patt)
            raise TypeError(msg)

        # stringify the code list for matching against the code pattern
        sep = " "  # the single whitespace delimiter, critical for pattern matching
        code_str = ""
        for e in evcodes:
            code_str += "{0}{1}".format(sep, e)

        # sweep the pattern regular expression across the code string
        matches = [m for m in patt_regx.finditer(code_str)]

        # rank of the sep delimiter == event code index
        # end boundary of nth sep delimiter is right-boundary of the nth event code
        delims = [m.end() for m in re.finditer(sep, code_str)]

        # assert len(delims)==len(evcodes) # very very bad if not
        if len(delims) != len(evcodes):
            msg = (
                "something has gone horribly wrong in _find_event_codes(), "
                "stop what you"
                "re doing immediately, find urbach "
                "and smack him up side the head."
            )
            raise ValueError(msg)

        # 3. scan the string delimter values for pattern match span starts
        for (didx, delim_at) in enumerate(delims):

            # A search may find 0, 1, or 1+ pattern
            # match(es). If a match is found there is at least one
            # match group for the obligatory anchor and maybe more
            # if the pattern contains additional capture groups.
            # So for generality always iterate over m.groups()
            for m in matches:
                if delim_at == m.span()[0]:
                    m_group_info = []

                    # iterate thru the match groups in this m
                    mgi = 1  # individual match groups start at index 1

                    # copy indexes to process m's match groups
                    # w/out disturbing didx, delim_at
                    idx = didx
                    dlim = delim_at

                    anchor_idx, anchor_group_idx, anchor_tick = (
                        None,
                        None,
                        None,
                    )

                    #  this index points to the anchor capture group in m.groups()
                    anchor_group_idx = anchor[0] + 1

                    # for readability
                    anchor_delim = m.span(anchor_group_idx)[
                        0
                    ]  # string offset for anchor
                    anchor_idx = delims.index(
                        anchor_delim
                    )  # index in code list of anchor
                    anchor_tick = ticks[anchor_idx]  # index into the lists

                    # assert(int(m.group(anchor_group_idx)) == evcodes[anchor_idx])
                    # confirm stringified event code sequence w/ original array
                    if int(m.group(anchor_group_idx)) != evcodes[anchor_idx]:
                        msg = (
                            "uh oh, horrible bug #1 in the event code finder "
                            "... yell at urbach"
                        )
                        raise ValueError(msg)

                    while mgi <= m.lastindex and idx < len(evcodes):
                        if m.start(mgi) == dlim:
                            # scrape this match group info
                            info = None

                            # capture groups match one or more evcodes
                            # ... make a list, possibly singleton
                            enumevcodes = [
                                (i, c)
                                for i, c in enumerate(
                                    m.group(mgi).strip().split(" ")
                                )
                            ]

                            # check the slicing and dicing ...
                            # the code (sequence) at this index must match the string pattern
                            # assert all([c == str(evcodes[idx+i]) for i,c in enumevcodes])
                            if any(
                                [
                                    c != str(evcodes[idx + i])
                                    for i, c in enumevcodes
                                ]
                            ):
                                msg = (
                                    "uh oh, horrible bug #2 in the event code finder"
                                    "... yell at urbach"
                                )
                                raise ValueError(msg)

                            # whew ...
                            for i, c in enumevcodes:
                                # each info is a list of (key, value) tuples, readily
                                # convertible something useful ... OrderedDict, pandas.Dataframe
                                info = [
                                    ("match_group", mgi),
                                    ("idx", idx),
                                    ("dlim", dlim),
                                    ("anchor_str", m.group(anchor_group_idx)),
                                    ("match_str", m.group(mgi)),
                                    ("anchor_code", evcodes[anchor_idx]),
                                    (
                                        "match_code",
                                        evcodes[idx + i],
                                    ),  # evcodes[idx],
                                    ("anchor_tick", anchor_tick),
                                    (
                                        "match_tick",
                                        ticks[idx + i],
                                    ),  # ticks[idx]
                                    (
                                        "anchor_tick_delta",
                                        int(ticks[idx + i]) - int(anchor_tick),
                                    ),
                                    ("is_anchor", mgi == anchor_group_idx),
                                ]
                                m_group_info.append(info)
                            mgi += 1
                        idx += 1  # keep looking to the right
                        if idx == len(evcodes):
                            continue  # nothing else to look for, move on
                        dlim = delims[idx]  # update delimiter

                        # vestigal bounds check ...
                        if idx > len(evcodes):
                            msg = (
                                "uh oh, event code list overrun horrible bug #3 in the "
                                "event code finder ... yell at urbach"
                            )
                            raise ValueError(msg)

                    # accumulate the data
                    rvals.append(m_group_info)

        # done scanning, go home
        if len(rvals) > 0:
            # pp.pprint(rvals)
            # pdb.set_trace()
            return rvals
        else:
            return None
