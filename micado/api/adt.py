"""

Low-level methods for ADTs:

applications()
validate()
translate()
submit()
diff()
delete()
clean()

"""


class ADTMixin:
    def applications(self):
        url = self._url("/list_app")
        resp = self.get(url)
        return resp.json()["message"]