"""
Higher-level methods to manage the MiCADO node
"""
import os
from pathlib import Path

from micado.utils.utils import DataHandling

from ..api.client import SubmitterClient
from .base import Model

DEFAULT_PATH = Path.home() / ".micado-cli"


class Micado(Model):
    home = str(Path(os.environ.get("MICADO_CLI_DIR", DEFAULT_PATH))) + "/"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def micado_id(self):
        return self.client.micado_id

    @micado_id.setter
    def micado_id(self, micado_id):
        self.client.micado_id = micado_id

    @property
    def micado_ip(self):
        return self.client.micado_ip

    @micado_ip.setter
    def micado_ip(self, micado_ip):
        self.client.micado_ip = micado_ip

    @property
    def details(self):
        return self.client.details
    
    @details.setter
    def details(self, details):        
        self.client.details = details

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
        server = DataHandling.get_properties(f"{self.home}data.yml", self.micado_id)
        self.micado_ip = server["ip"]
        
        self.details = f"""
        WebUI: https://{server["ip"]}
        Username: {server["micado_user"]}
        Password: {server["micado_password"]}
        """
        
        return SubmitterClient(
            endpoint=server["endpoint"],
            version=server["api_version"],
            verify=server["cert_path"],
            auth=(server["micado_user"], server["micado_password"]),
        )

    def attach(self, micado_id):
        """Configure the micado object to handle the instance
        created by the def:create()

        Args:
            micado_id (string): micado ID returned by def:create()
        """
        self.micado_id = micado_id
        self.api = self.init_api()

    def create(self, **kwargs):
        """Creates a new MiCADO VM and deploy MiCADO services on it.

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

            >>> client.micado.create(
            ...     auth_url='yourendpoint',
            ...     project_id='project_id',
            ...     image='image_name or image_id',
            ...     flavor='flavor_name or flavor_id',
            ...     network='network_name or network_id',
            ...     keypair='keypair_name or keypair_id',
            ...     security_group='security_group_name or security_group_id'
            ... )

        Returns:
            string: ID of MiCADO

        """
        try:
            _micado = self.launcher.launch(**kwargs)
            self.micado_id = _micado.id
            self.micado_ip = _micado.ip

            self.installer.deploy(_micado, **kwargs)
            self.api = self.init_api()
        except Exception as e:
            if hasattr(locals()["self"], "micado_id"):
                self.launcher.delete(self.micado_id)
            raise
        return self.micado_id

    def destroy(self):
        """Destroy running applications and the existing MiCADO VM.

        Usage:

            >>> client.micado.destroy()

        """
        self.api = self.init_api()
        self.api._destroy()
        self.api = None
        self.launcher.delete(self.micado_id)
