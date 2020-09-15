from .devstack import *

MEDIA_ROOT = "%(EDXROOT)s/uploads/"  # TODO is this useful?
FEATURES["ENABLE_DISCUSSION_SERVICE"] = False
