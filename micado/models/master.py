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
        """
        call lower level methods to create a MiCADO master
        point to the created submitter API
        """
        self.id = self.launcher.launch(**kwargs)
        api_end = self.launcher.get_api_endpoint(self.id)
        api_vers = self.launcher.get_api_version()

        self.api = SubmitterClient(endpoint=api_end, version=api_vers)

    def destroy(self, **kwargs):
        """
        call lower level methods to ddelete a MiCADO master
        remove the associated API object
        """
        self.api = None
        self.launcher.delete(**kwargs)
