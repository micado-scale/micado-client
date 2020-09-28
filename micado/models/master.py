"""
Higher-level methods to manage the MiCADO master
"""

from .base import Model

from ..api.client import SubmitterClient


class MicadoMaster(Model):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def launcher(self):
        return self.client.launcher

    @property
    def api(self):
        return self.client.api

    @api.setter
    def api(self, api):
        self.client.api = api

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

        """

        self.id = self.launcher.launch(**kwargs)
        api_end = self.launcher.get_api_endpoint(self.id)
        api_vers = self.launcher.get_api_version()

        self.api = SubmitterClient(endpoint=api_end, version=api_vers)

    def destroy(self, **kwargs):
        """Destroy the existing MiCADO master VM.

        Args:
            id (string): The MiCADO master UUID.
            auth_url (string): Authentication URL for the NOVA
                resource.
            region (string, optional): Name of the region resource.
                Defaults to None.
            user_domain_name (string, optional): Define the user_domain_name.
                Defaults to 'Default'
            project_id (string, optional): ID of the project resource.
                Defaults to None.
        """

        self.api = None
        self.launcher.delete(**kwargs)
