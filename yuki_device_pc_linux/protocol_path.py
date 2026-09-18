import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROTOCOL_PATH = os.path.normpath(os.path.join(_THIS_DIR, "..", "libs", "yuki-protocol", "python"))
if _PROTOCOL_PATH not in sys.path:
    sys.path.insert(0, _PROTOCOL_PATH)
