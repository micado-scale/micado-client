"""
Local representation of an ADT 
add_node()
add_policy()
check_tosca()

and simplify calls to low-level API
deploy() (ie. validate(), translate(), submit())
update() (ie. validate(), translate(), diff(), submit())
delete() (ie. delete(), clean())
"""

from .base import Model

class Application(Model):

    def list(self):
        return self.client.api.applications()
