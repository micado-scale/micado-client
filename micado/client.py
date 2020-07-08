"""

Higher-level client for both submitter interaction and launching ability

"""

import os

from .api.client import SubmitterClient

from .launcher.libcloud import LibCloudLauncher
from .launcher.occopus import OccopusLauncher

from .models.application import Application
from .models.cluster import MicadoCluster

from .utils.utils import check_launch
from .exceptions import MicadoException

LAUNCHERS = {
    "libcloud": LibCloudLauncher,
    "occopus": OccopusLauncher,
}

class MicadoClient:
    """
    Usage with a launcher:

        >> import micado
        >> client = micado.MicadoClient(launcher="libcloud")
        >> client.cluster().create()
        >> client.applications().list()
        >> client.cluster().destroy()

    Usage without a launcher:

        >> import micado
        >> client = micado.MicadoClient(endpoint="http://micado:5050/" version="v1.0")
        >> client.applications().list()    
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
        """
        Usage:
            >> client = micado.MicadoClient.from_master() if ENVIRO below is set
        """
        try:
            submitter_endpoint = os.environ["MICADO_API_ENDPOINT"]
            submitter_version = os.environ["MICADO_API_VERSION"]
        except KeyError as err:
            raise MicadoException(f"Environment variable {err} not defined!")

        return cls(endpoint=submitter_endpoint, version=submitter_version)

    @check_launch
    def applications(self):
        return Application(client=self)

    def cluster(self):
        if not self.launcher:
            raise MicadoException("No launcher defined")
        return MicadoCluster(client=self)