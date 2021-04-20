"""
Higher-level methods to manage the MiCADO master
"""
import os
from pathlib import Path

from micado.utils.utils import DataHandling

from ..api.client import SubmitterClient
from .base import Model

DEFAULT_PATH = Path.home() / ".micado-cli"


class MicadoMaster(Model):
    home = str(Path(os.environ.get("MICADO_CLI_DIR", DEFAULT_PATH))) + '/'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def master_id(self):
        return self.client.master_id

    @master_id.setter
    def master_id(self, master_id):
        self.client.master_id = master_id

    @property
    def launcher(self):
        return self.client.launcher

    @property
    def installer(self):
        return self.client.installer

    @property
    def api(self):
        return self.client.api

    @api.setter
    def api(self, api):
        self.client.api = api

    def init_api(self):
        """Configure Submitter API

        Returns:
            SubmitterClient: return SubmitterClient
        """
        server = DataHandling.get_properties(
            f'{self.home}data.yml', self.master_id)
        return SubmitterClient(endpoint=server["endpoint"],
                               version=server["api_version"],
                               verify=server["cert_path"],
                               auth=(server["micado_user"],
                                     server["micado_password"]))

    def attach(self, master_id):
        """Configure the master object to handle the instance
        created by the def:create()

        Args:
            master_id (string): master ID returned by def:create()
        """
        self.master_id = master_id
        self.api = self.init_api()

    def create(self, **kwargs):
        """Creates a new MiCADO master VM and deploy MiCADO service on it.

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

        Usage:

            >>> client.master.create(
            ...     auth_url='yourendpoint',
            ...     project_id='project_id',
            ...     image='image_name or image_id',
            ...     flavor='flavor_name or flavor_id',
            ...     network='network_name or network_id',
            ...     keypair='keypair_name or keypair_id',
            ...     security_group='security_group_name or security_group_id'
            ... )

        Returns:
            string: ID of MiCADO master

        """
        self.master_id = self.launcher.launch(**kwargs)
        self.installer.deploy(self.master_id, **kwargs)
        self.api = self.init_api()
        return self.master_id

    def destroy(self):
        """Destroy running applications and the existing MiCADO master VM.

        Usage:

            >>> client.master.destroy()

        """
        self.api = self.init_api()
        self.api._destroy()
        self.api = None
        self.launcher.delete(self.master_id)
