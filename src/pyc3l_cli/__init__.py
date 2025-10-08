## Monkey-patching parsimonious 0.8 to support Python 3.11

import warnings

warnings.filterwarnings("ignore")


import sys
import inspect

# Check if we're running on Python 3.11 or later
if sys.version_info >= (3, 11):
    # Implement a getargspec function using getfullargspec for compatibility
    def getargspec(func):
        full_argspec = inspect.getfullargspec(func)
        args = full_argspec.args
        varargs = full_argspec.varargs
        varkw = full_argspec.varkw
        defaults = full_argspec.defaults
        return inspect.ArgSpec(args, varargs, varkw, defaults)

    # Monkey patch the inspect module
    inspect.getargspec = getargspec

## End of monkey-patching parsimonious
