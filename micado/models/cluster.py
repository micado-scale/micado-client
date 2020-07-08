"""
Higher-level methods to manage the MiCADO cluster
"""

from .base import Model

from ..api.client import SubmitterClient

class MicadoCluster(Model):

    @property
    def launcher(self):
        return self.client.launcher

    @property
    def api(self):
        return self.client.api

    @api.setter
    def api(self, api):
        self.client.api = api

    def create(self):
        """
        call lower level methods to create a MiCADO master
        point to the created submitter API
        """
        self.launcher.launch()
        api_end = self.launcher.get_api_endpoint()
        api_vers = self.launcher.get_api_version()

        self.api = SubmitterClient(endpoint=api_end, version=api_vers)


    def destroy(self):
        """
        call lower level methods to ddelete a MiCADO master
        remove the associated API object
        """
        self.api = None
        self.launcher.delete()