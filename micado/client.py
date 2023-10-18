"""

Higher-level client for both submitter interaction and launching ability

"""

import os

from .api.client import SubmitterClient

from .launcher.openstack import OpenStackLauncher
from .launcher.cloudbroker import CloudBrokerLauncher

from .installer.ansible import AnsibleInstaller

from .models.application import Applications
from .models.micado import Micado

from .exceptions import MicadoException

LAUNCHERS = {
    "openstack": OpenStackLauncher,
    "cloudbroker": CloudBrokerLauncher,
}

INSTALLER = {
    "ansible": AnsibleInstaller,
}


class MicadoClient:
    """The MiCADO Client

    Builds and communicates with a MiCADO node

    Usage with a launcher:

    a)

        >>> from micado import MicadoClient
        >>> client = MicadoClient(launcher="openstack", installer="ansible")
        >>> client.micado.create(
        ...     auth_url='yourendpoint',
        ...     project_id='project_id',
        ...     image='image_name or image_id',
        ...     flavor='flavor_name or flavor_id',
        ...     network='network_name or network_id',
        ...     keypair='keypair_name or keypair_id',
        ...     security_group='security_group_name or security_group_id'
        ... )
        >>> client.applications.list()
        >>> client.micado.destroy()

    b)

        >>> from micado import MicadoClient
        >>> client = MicadoClient(launcher="openstack", installer="ansible")
        >>> micado_id = client.micado.create(
        ...     auth_url='yourendpoint',
        ...     project_id='project_id',
        ...     image='image_name or image_id',
        ...     flavor='flavor_name or flavor_id',
        ...     network='network_name or network_id',
        ...     keypair='keypair_name or keypair_id',
        ...     security_group='security_group_name or security_group_id'
        ... )
        >>> client.applications.list()
        >>> << store your micado_id >>
        >>> << exit >>
        >>> -------------------------------------------------------------
        >>> << start >>
        >>> ...
        >>> micado_id = << retrieve micado_id >>
        >>> client = MicadoClient(launcher="openstack", installer="ansible")
        >>> client.micado.attach(micado_id = micado_id)
        >>> client.applications.list()
        >>> client.micado.destroy()

    c)

        >>> from micado import MicadoClient
        >>> client = MicadoClient(launcher="cloudbroker", installer="ansible")
        >>> client.micado.create(
        ...     auth_url='yourendpoint',
        ...     deployment_id='deployment_id',
        ...     instance_type_id='image_name or image_id',
        ...     key_pair_id='key_pair_id',
        ...     firewall_rule_set_id='firewall_rule_set_id',
        ... )
        >>> client.applications.list()
        >>> client.micado.destroy()


    Usage without a launcher i.e. MiCADO is already created independently from the client library.

        >>> from micado import MicadoClient
        >>> client = MicadoClient(
        ...     endpoint="https://micado/toscasubmitter/",
        ...     version="v2.0",
        ...     verify=False,
        ...     auth=("ssl_user", "ssl_pass")
        ... )
        >>> client.applications.list()

    Args:
        auth_url (string): Authentication URL for the NOVA
            resource.
        image (string): Name or ID of the image resource.
        flavor (string): Name or ID of the flavor resource.
        network (string): Name or ID of the network resource.
        keypair (string): Name or ID of the keypair resource.
        security_group (string, optional): name or ID of the
            security_group resource. Defaults to 'all'.
        region (string, optional): Name of the region resource.
            Defaults to None.
        user_domain_name (string, optional): Define the user_domain_name.
            Defaults to 'Default'
        project_id (string, optional): ID of the project resource.
            Defaults to None.
        micado_user (string, optional): MiCADO username.
            Defaults to admin.
        micado_password (string, optional): MiCADO password.
            Defaults to admin.
        enable_terraform (bool, optional): Enable terraform in the deployment.
            Defaults to False.
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
            try:
                installer = kwargs.pop("installer", "").lower()
                if installer != '':
                    self.installer = INSTALLER[installer]()
            except KeyError:
                raise MicadoException(f"Unknown installer: {installer}")
        else:
            self.api = SubmitterClient(*args, **kwargs)

    @classmethod
    def from_env(cls):
        """Usage:
            Ensure MICADO_API_ENDPOINT and MICADO_API_VERSION
            environment variables are set, then:

            >>> from micado import MicadoClient
            >>> client = MicadoClient.from_env()
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

    @classmethod
    def from_existing(
        cls,
        endpoint,
        version="v2.0",
        username="admin",
        password="admin",
        cert=False
    ):
        """Usage:
            Use endpoint, API version, user/pass & verify

            >>> from micado import MicadoClient
            >>> client = MicadoClient.from_existing()
        """

        return cls(
            endpoint=endpoint,
            version=version,
            auth=(username, password),
            verify=cert,
        )

    @property
    def applications(self):
        return Applications(client=self)

    @property
    def micado(self):
        if not self.launcher:
            raise MicadoException("No launcher defined")
        return Micado(client=self)
