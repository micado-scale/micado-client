"""
Low-level MiCADO API client, to be used by higher-level ..client
"""

import requests

from .adt import ADTMixin


class SubmitterClient(requests.Session, ADTMixin):
    """Low-level MiCADO client

    """

    def __init__(self, endpoint=None, version=None):
        super().__init__()
        self.endpoint = endpoint.strip("/") + "/"
        self._version = version

    def _url(self, path):
        return self.endpoint + self._version + path


