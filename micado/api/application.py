"""

Low-level methods for managing applications in MiCADO

"""
import json

from micado.types import ApplicationInfo
from micado.exceptions import detailed_raise_for_status

class ApplicationMixin:
    def applications(self):
        """Lists the currently running applications

        Returns:
            list: Current application IDs
        """
        url = self._url("/applications/")
        resp = self.get(url)
        detailed_raise_for_status(resp)
        return resp.json()["applications"]

    def inspect_app(self, app_id):
        """Fetches detailed info on an application

        Args:
            app_id (string): The ID of the application

        Returns:
            dict: Info on the given application
        """
        url = self._url(f"/applications/{app_id}/")
        resp = self.get(url)
        detailed_raise_for_status(resp)
        return resp.json()

    def create_app(
        self, app_id=None, adt=None, url=None, params=None, dryrun=False, file=None
    ):
        """Creates/deploys an application in MiCADO

        Args:
            app_id (string, optional): The ID of the application to deploy.
                Defaults to None.
            adt (dict, optional): YAML dict of the application description
                template. Required if no URL or file provided. Defaults to None.
            url (string, optional): URL to YAML document of the ADT.
                Required if no adt(dict) or file is provided. Defaults to None.
            params (dict, optional): Dict of TOSCA input values.
                Defaults to None.
            dryrun (bool, optional): Flag to skip execution of components.
                Defaults to False.
            file (string, optional): YAML or CSAR file to submit. Required
                if no adt(dict) or URL is provided. Defaults to None.

        Raises:
            TypeError: If no ADT/URL data is passed in

        Returns:
            dict: ID and status of deployed application
        """
        if not adt and not url and not file:
            raise TypeError("Either adt or url or file is required.")
        if app_id:
            endpoint = self._url(f"/applications/{app_id}/")
        else:
            endpoint = self._url("/applications/")

        json_data = ApplicationInfo(adt, url, params, dryrun)
        if file:
            form_data = {
                k: json.dumps(v) if isinstance(v, dict) 
                else str(v) 
                for k, v in json_data.items()
            }
            file_data = {"adt": file}
            resp = self.post(endpoint, files=file_data, data=form_data)
        else:
            resp = self.post(endpoint, json=json_data)
        detailed_raise_for_status(resp)
        return resp.json()

    def delete_app(self, app_id, force=False):
        """Delete an application in MiCADO

        Args:
            app_id (string): ID of application to delete
            force (bool, optional): Ignore errors. Defaults to False.

        Returns:
            dict: ID and status of deletion
        """
        url = self._url(f"/applications/{app_id}/")
        json_data = {"force": force}
        resp = self.delete(url, json=json_data)
        if not force:
            detailed_raise_for_status(resp)
        return resp.json()

    def _destroy(self):
        """Deletes all application in MiCADO

        This should normally only be called by a launcher that
        is ready to destroy the entire MiCADO stack
        """
        app_ids = self.applications()
        for app in app_ids:
            self.delete_app(app, force=True)
