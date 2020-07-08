"""
Low-level methods for handling a MiCADO cluster with Apache LibCloud
"""
class LibCloudLauncher:
    """
    For launching a MiCADO Master with Apache LibCloud
    """
    def launch(self):
        """
        Create the MiCADO Master node
        """
        return "Launched"

    def get_api_endpoint(self):
        """
        Return the MiCADO Master Submitter API endpoint
        """
        return "http://submitter:5050"

    def get_api_version(self):
        """
        Return the MiCADO Master Submitter API version
        """
        return "v1.0"

    def delete(self):
        """
        Destroy the MiCADO Master node
        """
        return "Destroyed"
