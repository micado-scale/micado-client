import random
import time
import uuid

from ruamel.yaml import YAML

from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider


"""
Low-level methods for handling a MiCADO master with Apache LibCloud
"""


class LibCloudLauncher:
    """
    For launching a MiCADO Master with Apache LibCloud
    """

    def launch(self, apiVersion, endpoint, authVersion, tenantName, imageID, flavor):
        """
        Create the MiCADO Master node
        """
        driver = self._get_driver(
            apiVersion, endpoint, authVersion, tenantName)
        image = driver.get_image(imageID)
        size = next((x for x in driver.list_sizes() if x.name == flavor), None)
        id = uuid.uuid1()
        if size is None:
            raise Exception("No such flavor.")
        node = driver.create_node(name='MiCADO-Master-{}'.format(id.hex), image=image, size=size,
                                  ex_config_drive=True, ex_keyname='emodi')
        print('The VM {} starting...'.format(node.id))
        max_attempt = 60
        waiting = 10
        attempts = 0
        floating_ips = self._get_floating_ip(driver)
        if not floating_ips:
            raise Exception("There is no free ip address.")
        floating_ip = random.choice(floating_ips)
        while attempts <= max_attempt:
            try:
                driver.ex_attach_floating_ip_to_node(node, floating_ip)
                print("Associating floating IP: {} to node: success. Took {} seconds.".format(
                    floating_ip.ip_address, attempts * waiting))
                print("Waiting VM running state...")
                break
            except Exception as e:
                print("Associating floating IP: {} to node failed. Elapsed {} second... Retrying...".format(
                    floating_ip.ip_address, attempts * waiting))
                attempts += 1
                time.sleep(waiting)
        if attempts > max_attempt:
            print("Gave up associating floating IP to node! Could not get it in {} seconds.".format(
                attempts*waiting))
        driver.wait_until_running([node])
        print("{} VM running".format(node.id))
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

    def delete(self, id, apiVersion, endpoint, authVersion, tenantName):
        """
        Destroy the MiCADO Master node
        """
        driver = self._get_driver(
            apiVersion, endpoint, authVersion, tenantName)
        delete_node = None
        # print(node)
        delete_node = next(
            (node for node in driver.list_nodes() if node.id == id), None)
        if delete_node is None:
            raise Exception("{} ID does not exist!".format(id))
        driver.destroy_node(delete_node)
        print('Dropping node {}'.format(id))
        return "Destroyed"

    def get_credentials(self):
        with open('auth_data.yml', 'r') as stream:
            yaml = YAML()
            code = yaml.load(stream)
        for iii in code['resources']:
            if iii['type'] == 'nova':
                auth_data = iii['auth_data']
                break
        if not auth_data or not 'username' in auth_data or not 'password' in auth_data:
            raise Exception(
                'Creadentials not found for NOVA api... Please use the template file')
        return auth_data

    def _get_floating_ip(self, driver):
        return [addr for addr in driver.ex_list_floating_ips() if addr.node_id is None]

    def _get_driver(self, apiVersion, endpoint, authVersion, tenantName):
        auth_data = self.get_credentials()
        OpenStack = get_driver(Provider.OPENSTACK)
        return OpenStack(auth_data['username'], auth_data['password'],
                         api_version=apiVersion,
                         ex_force_auth_url=endpoint,
                         ex_force_auth_version=authVersion,
                         ex_tenant_name=tenantName)
