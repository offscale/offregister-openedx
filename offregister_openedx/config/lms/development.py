from .devstack import *

MEDIA_ROOT = "%(EDXROOT)s/uploads/"  # FIXME
FEATURES["ENABLE_DISCUSSION_SERVICE"] = False
