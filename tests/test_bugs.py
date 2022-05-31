"""usage for replicable bugs that are supposed to be fixed"""

from pathlib import Path
from .config import TEST_DIR, IRB_DIR, GET_IRB_MKDIG, CAL_ARGS, irb_data, mkpy
from mkpy import mkh5


@irb_data
def test_irb_pcag_10y():
    """mkh5._read_raw_log() failed on these files. The clock tick for the
    last log event is larger by a few ticks than the number of samples
    in the crw. This is a log/crw dimension mismatch in the number of
    samples and also the number of event codes.

    """

    h5_f = IRB_DIR / "mkh5" / "pcag10ybug.h5"

    crw_f = IRB_DIR / "mkdig" / "pcag10y.crw"
    log_f = IRB_DIR / "mkdig" / "pcy10.x.log"
    yhdr_f = IRB_DIR / "mkdig" / "pcag10y.yhdr"

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()
    myh5.create_mkdata("10y", crw_f, log_f, yhdr_f)


@irb_data
def test_irb_pcag_13o():
    """mkh5.CodeMapper.get_event_table() failed on these files. The .h5
    creates fine, but the last dblock is 186 samples with no event
    codes. So in CodeMapper._find_event_codes() the "empty" evcodes
    list is [] while the "empty" delims is [' '].  So len(delims) ==
    1, len(evcodes) == 0 and assert len(delims) == len(evcodes)
    fails. Hacked in a guard but its really a logic bug in checking
    evcodes vs code_str and what counts as empty in delims.

    """

    h5_f = IRB_DIR / "mkh5" / "pcag13obug.h5"
    crw_f = IRB_DIR / "mkdig" / "pcag13o.crw"
    log_f = IRB_DIR / "mkdig" / "pco13.x.log"
    yhdr_f = IRB_DIR / "mkdig" / "pcag13o.yhdr"
    ytbl_f = TEST_DIR("data/simple.ytbl")
    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()
    myh5.create_mkdata("13o", crw_f, log_f, yhdr_f)
    event_table = myh5.get_event_table(ytbl_f)


@irb_data
def test_irb_hp301():
    """_find_events bombs out w/ an urbach slap"""

    subid = "hp301"
    h5_f = IRB_DIR / "mkh5" / (subid + ".h5")
    crw_f = IRB_DIR / "mkdig" / "hp301.crw"
    log_f = IRB_DIR / "mkdig" / "hp301.x.log"
    yhdr_f = IRB_DIR / "mkdig" / "hp301.yhdr"
    ytbl_f = TEST_DIR("data/HP3_Materials_PreScn_RegExp.xlsx!test")

    myh5 = mkh5.mkh5(h5_f)
    myh5.reset_all()
    myh5.create_mkdata("hp301", crw_f, log_f, yhdr_f)
    event_table = myh5.get_event_table(ytbl_f)
