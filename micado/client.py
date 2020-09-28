"""

Higher-level client for both submitter interaction and launching ability

"""

import os

from .api.client import SubmitterClient

from .launcher.occopus import OccopusLauncher
from .launcher.openstack import OpenStackLauncher

from .models.application import Applications
from .models.master import MicadoMaster

from .exceptions import MicadoException

LAUNCHERS = {
    "occopus": OccopusLauncher,
    "openstack": OpenStackLauncher,
}


class MicadoClient:
    """The MiCADO Client

    Builds and communicates with a MiCADO Master node

    Usage with a launcher:

        >>> import micado
        >>> client = micado.MicadoClient(launcher="libcloud")
        >>> client.master.create()
        >>> client.applications.list()
        >>> client.master.destroy()

    Usage without a launcher:

        >>> from micado import MicadoClient
        >>> client = MicadoClient(
        ...     endpoint="https://micado/toscasubmitter/",
        ...     version="v2.0",
        ...     verify=False,
        ...     auth=("ssl_user", "ssl_pass")
        ... )
        >>> client.applications.list()

        Args:
            endpoint (string): Full URL to API endpoint (omit version).
                Required.
            version (string, optional): MiCADO API Version (minimum v2.0).
                Defaults to 'v2.0'.
            verify (bool, optional): Verify certificate on the client-side.
                OR (str): Path to cert bundle (.pem) to verfiy against.
                Defaults to True.
            auth (tuple, optional): Basic auth credentials (<user>, <pass>).
                Defaults to None.
    """

    def __init__(self, *args, **kwargs):
        launcher = kwargs.pop("launcher", "").lower()
        if launcher:
            self.api = None
            try:
                self.launcher = LAUNCHERS[launcher]()
            except KeyError:
                raise MicadoException(f"Unknown launcher: {launcher}")
        else:
            self.api = SubmitterClient(*args, **kwargs)

    @classmethod
    def from_master(cls):
        """Usage:
            >>> from micado import MicadoClient
            >>> client = MicadoClient.from_master() if ENV below is set
        """
        try:
            submitter_endpoint = os.environ["MICADO_API_ENDPOINT"]
            submitter_version = os.environ["MICADO_API_VERSION"]
        except KeyError as err:
            raise MicadoException(f"Environment variable {err} not defined!")

        return cls(
            endpoint=submitter_endpoint,
            version=submitter_version,
            verify=False,
        )

    @property
    def applications(self):
        return Applications(client=self)

    @property
    def master(self):
        if not self.launcher:
            raise MicadoException("No launcher defined")
        return MicadoMaster(client=self)
