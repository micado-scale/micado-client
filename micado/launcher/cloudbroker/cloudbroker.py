#!/usr/bin/env python

import logging
import logging.config
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse
from time import sleep
import itertools as it
import xml.dom.minidom
from xml.dom.minidom import parseString
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.etree.ElementTree as ET
from dicttoxml import dicttoxml
from collections import OrderedDict
import requests, json
import base64
from micado.types.micado import MicadoInfo
from micado.exceptions import MicadoException
from micado.utils.utils import DataHandling, SSHKeyHandling
import ruamel.yaml as yaml

"""
Low-level methods for handling a MiCADO node with CloudBroker API
"""
DEFAULT_PATH = Path.home() / ".micado-cli"
DEFAULT_VERS = "0.9.1-rev1"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
micado_cli_dir = Path(os.environ.get("MICADO_CLI_DIR", DEFAULT_PATH))
micado_cli_dir.mkdir(parents=True, exist_ok=True)
ch = logging.StreamHandler()
fh = logging.handlers.RotatingFileHandler(
    filename=str(micado_cli_dir / "micado-cli.log"),
    mode="a",
    maxBytes=52428800,
    backupCount=3,
)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s : %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)


class CloudBrokerLauncher:
    """
    For launching a MiCADO node with CloudBroker API
    """
    home = str(Path(os.environ.get("MICADO_CLI_DIR", DEFAULT_PATH))) + '/'

    def launch(self, 
               auth_url, 
               name=None, 
               deployment_id=None, 
               instance_type_id=None, 
               key_pair_id=None, 
               firewall_rule_set_id=None, 
               **kwargs):
        """
        Create the MiCADO node

        Args:
            name (string): Optional name for the MiCADO instance
            auth_url ([type]): [description]
            deployment_id ([type]): [description]
            instance_type_id ([type]): [description]
            key_pair_id ([type]): [description]
            firewall_rule_set_id ([type]): [description]

        Returns:
            MicadoInfo: Dataclass with MiCADO ID and IP
        """
        instanceID = ""

        try:
            pub_key = SSHKeyHandling.get_pub_key(self.home)
            if deployment_id is None:
                raise MicadoException("Can't find deployment id!")
            if instance_type_id is None:
                raise MicadoException("Can't find instance type id!")
            if key_pair_id is None:
                raise MicadoException("Can't find key pair id!")
            if firewall_rule_set_id is None:
                raise MicadoException("Can't find firewall rule set id!")

            descr = {}
            descr['deployment_id'] = deployment_id
            descr['instance_type_id'] = instance_type_id
            descr['key_pair_id'] = key_pair_id
            descr['firewall_rule_set_id'] = firewall_rule_set_id
            descr.setdefault('disable_autostop', 'true')
            descr.setdefault('isolated', 'true')
            if not name:
                name_id = uuid.uuid1()
                name = 'MiCADO-{}'.format(name_id.hex)
            descr['name'] = name

            logger.info('Creating CloudBroker VM...')
            cloud_init_config = """
            #cloud-config

            ssh_authorized_keys:
            - {}
            """.format(pub_key)

            descr['cloud-init'] = base64.b64encode(cloud_init_config.encode('utf-8')).decode('utf-8')
            descr['cloud-init-b64'] = 'true'

            logger.debug("XML to pass to CloudBroker: %s", dicttoxml(descr, custom_root='instance', attr_type=False))
            r = requests.post(auth_url + '/instances.xml',
                              dicttoxml(descr, custom_root='instance', attr_type=False),
                              auth=self.get_auth(),
                              headers={'Content-Type': 'application/xml'})            

            logger.debug('CloudBroker instance create response status code %d, response: %s', r.status_code, r.text)
            if (r.status_code == 201):
                DOMTree = xml.dom.minidom.parseString(r.text)
                instance = DOMTree.documentElement
                instanceID = instance.getElementsByTagName('id')[0].childNodes[0].data
                logger.info("CloudBroker instance started, instance id: %s", instanceID)
                mstate = "starting"
                while mstate != "running":
                    sleep(5)
                    instance = self.get_instance(auth_url, instanceID)
                    mstate = self.getTagText(instance.getElementsByTagName('status').item(0).childNodes)
                floating_ip_address = self.getTagText(instance.getElementsByTagName('external-ip-address').item(0).childNodes)
                self._persist_data(floating_ip_address, instanceID, auth_url, deployment_id, instance_type_id, key_pair_id, firewall_rule_set_id)
                return MicadoInfo(instanceID, floating_ip_address)
            else:
                errormsg = 'Failed to create CloudBroker instance, request status code {0}, response: {1}'.format(r.status_code, r.text)
                logger.debug(errormsg)
                raise Exception(errormsg)

        except MicadoException as e:
            logger.error(f"Exception cought: {e}")
            raise
        except Exception as e:
            logger.error(f"Exception cought: {e}")
            raise

    def delete(self, id):
        """
        Destroy the existing MiCADO VM.
        Args:
            id (string): The MiCADO UUID.
        Raises:
            MicadoException: Missing or incorrect data.
        """
        try:
            auth_url = None
            content = None
            with open(self.home + 'data.yml', mode='r') as f:
                content = yaml.safe_load(f)
            search = [i for i in content["micados"] if i.get(id, None)]
            if not search:
                logger.debug(
                    "This {} ID can not find in the data file.".format(id))
                pass
            else:
                logger.debug("Remove {} record".format(search))
                auth_url = search[0][id]["auth_url"]
                content["micados"].remove(search[0])
                with open(self.home + 'data.yml', mode='w') as f:
                    yaml.dump(content, f)

            r = requests.put(auth_url + '/instances/' + id + '/stop.xml', auth=self.get_auth())
            logger.info('Dropping node {}'.format(id))
            if os.path.isfile(self.home + id + '-ssl.pem'):
                logger.info("remove {}-ssl.pem".format(self.home + id))
                os.remove(self.home + id + '-ssl.pem')
            return "Destroyed"
        except MicadoException as e:
            logger.error(f"Exception cought: {e}")

    def _get_credentials(self):
        """
        Read CloudBroker credentials from file.
        Usage : auth_data = self._get_credentials()
        """
        with open(self.home + "credentials-cloud-api.yml", "r") as stream:
            temp = yaml.safe_load(stream)

        resources = temp.get("resource", {})
        for resource in resources:
            if resource.get("type") == "cloudbroker":
                return resource.get("auth_data")

    def get_auth(self):
        auth_data = self._get_credentials()
        if (not auth_data) or (not "email" in auth_data) or (not "password" in auth_data):
            errormsg = "Cannot find credentials for CloudBroker. Please specify"
            logger.debug(errormsg)
        return (auth_data['email'], auth_data['password'])

    def _persist_data(self, floating_ip_address, instanceID, auth_url, deployment_id, instance_type_id, key_pair_id, firewall_rule_set_id):
        """
        """
        endpoint = f'https://{floating_ip_address}/toscasubmitter'
        file_location = self.home + "data.yml"
        DataHandling.persist_data(path=file_location,
                                  server_id=instanceID,
                                  ip=floating_ip_address,
                                  auth_url=auth_url,
                                  deployment_id=deployment_id,
                                  instance_type_id=instance_type_id,
                                  key_pair_id=key_pair_id,
                                  firewall_rule_set_id=firewall_rule_set_id,
                                  endpoint=endpoint)

    def get_instance(self, auth_url, instanceid):
        attempt = 0
        stime = 1
        while attempt < 5:
            query_str = auth_url + '/instances/' + instanceid + '.xml'
            r = requests.get(query_str, auth=self.get_auth())
            if (r.status_code != 200):
                logger.debug('CloudBroker API call failed! query: %s, status code %d, response: %s', query_str, r.status_code, r.text)
            else:
                DOMTree = xml.dom.minidom.parseString(r.text)
                instance = DOMTree.documentElement
                if 0 != instance.getElementsByTagName('id').length:
                    return instance
                else:
                    logger.debug('CloudBroker API returned incorrect answer! No instance id is found.query: %s, status code %d, response: %s', query_str, r.status_code, r.text)
            sleep(stime)
            stime = stime * 2
            attempt += 1
            logger.debug('Retry calling the CloudBroker API...')
        errormsg = 'Error in querying instance \'{0}\' {1} times through CloudBroker API at \'{2}\'.'.format(
               str(instanceid), str(attempt), auth_url)
        logger.debug(errormsg)
        raise Exception(errormsg)

    def getTagText(self, nodelist):
        rc = []
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return ''.join(rc)
