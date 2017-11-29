from .aws import *
MEDIA_ROOT = "%(EDXROOT)s/uploads/" # TODO: is this useful?
FEATURES['ENABLE_DISCUSSION_SERVICE'] = False

ALLOWED_HOSTS = [
    ENV_TOKENS.get('CMS_BASE'),
]
