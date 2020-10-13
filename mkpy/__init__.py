"""
Python utilities for data processing of .crw/.log/.arf files.

This __init__.py file in particular implements some logging facilities that can
be used throughout mkpy.
"""
import logging
import functools
from datetime import datetime
from pathlib import Path
import sys
import traceback
from pprint import pformat
import re
from . import dpath

__version__ = "0.2.4.dev3"


def get_ver():
    # check semantic version format in __init__.py and meta.yaml matches
    pf_ver = re.search(r"(?P<ver_str>\d+\.\d+\.\d+\S*)", __version__)

    if pf_ver is None:
        msg = f"""Illegal  __version__: {__version__}
        spudtr __init__.py must have an X.Y.Z semantic version, e.g.,

        __version__ = '0.0.0'
        __version__ = '0.0.0.dev0'
        __version__ = '0.0.0rc1'

        """
        raise Exception(msg)

    ver_str = pf_ver["ver_str"]

    return ver_str


# log names are timestamps
current_datetime = datetime.now().strftime("%m-%d-%y_%H:%M:%S")

# .mkpy in the home dir is used to store mkpy-specific files
home_dir = Path.home()
base_dir = home_dir.joinpath(".mkpy")
Path(base_dir).mkdir(parents=True, exist_ok=True)

# declare subdirectories here
log_dir = base_dir.joinpath("logs")

# create subdirectories here
Path(log_dir).mkdir(parents=True, exist_ok=True)

# .log files will be put in ~/.mkpy/logs and have timestamps for filenames
log_filename = log_dir.joinpath(current_datetime).with_suffix(".log")
logging.basicConfig(filename=log_filename, format="%(message)s", level=logging.DEBUG)


def current_function():
    """Returns the name of the calling function.

    Example:
        def caller():
            print(current_function())

        >>> caller()
        'caller'
    """
    return sys._getframe(1).f_code.co_name


def indent(level, text):
    """Returns text with each line indented 'level' number of times."""

    fstring = level * "\t" + "{}"
    return "".join([fstring.format(l) for l in text.splitlines(True)])


def log_exceptions(indent_level):
    """This decorator turns on exception logging for a wrapped function.

    Examples

      .. code-block:: python

         @log_exceptions()
         def function():
             return 0

    This will turn on exception logging and the traceback in the log file will
    be indented with one tab. To specify deeper levels of indentation, use the
    indent_level parameter:
    
    .. code-block:: python

       @log_exceptions(indent_level=2)
       def function2():
           return 0
    """

    def inner_decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            logging.info(
                indent(level=indent_level, text="FUNCTION " + function.__name__)
            )

            try:
                return function(*args, **kwargs)
            except:
                # log the traceback
                msg = "Exception in  " + function.__name__ + ":\n"
                msg += traceback.format_exc()
                logging.critical(indent(level=indent_level + 1, text=msg))

                # if DEBUG (or lower) logging level set, log the arguments
                logging.debug(
                    indent(level=indent_level + 1, text="Positional arguments:")
                )
                for i, arg in enumerate(args):
                    text = "Argument " + str(i) + ":"
                    logging.debug(indent(level=indent_level + 2, text=text))
                    logging.debug(indent(level=indent_level + 3, text=pformat(arg)))
                if kwargs:
                    logging.debug(
                        indent(level=indent_level + 1, text="Keyword arguments:")
                    )
                    for kwarg in kwargs:
                        text = kwarg + ":"
                        logging.debug(indent(level=indent_level + 2, text=text))
                        logging.debug(
                            indent(level=indent_level + 3, text=pformat(kwarg))
                        )

                # reraise the original exception
                raise

        return wrapper

    return inner_decorator
