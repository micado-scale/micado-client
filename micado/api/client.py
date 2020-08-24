"""

Low-level MiCADO API client, to be used by the higher-level ..client

"""

import requests

from .application import ApplicationMixin


class SubmitterClient(requests.Session, ApplicationMixin):
    """Low-level MiCADO client

    """

    def __init__(self, endpoint, version="v2.0", verify=True, auth=None):
        super().__init__()
        self.endpoint = endpoint.strip("/") + "/"
        self._version = version
        self.verify = verify
        if isinstance(auth, tuple):
            self.auth = auth
        elif auth:
            raise TypeError("Basic auth must be a tuple of (<user>, <pass>)")

    def _url(self, path):
        return self.endpoint + self._version + path
