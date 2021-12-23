#!/usr/bin/env python

import logging
import logging.config
import os
import random
import subprocess
import time
import uuid
from pathlib import Path

import requests
from keystoneauth1 import session
from micado.exceptions import MicadoException
from micado.utils.utils import DataHandling, SSHKeyHandling
from novaclient import client as nova_client
from ruamel.yaml import YAML

import openstack
from openstack import connection

from .auth import AUTH_TYPES
from micado.types.micado import MicadoInfo

"""Low-level methods for handling a MiCADO node with OpenStackSDK

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


class OpenStackLauncher:
    """For launching a MiCADO node with OpenStackSDK

    """
    home = str(Path(os.environ.get("MICADO_CLI_DIR", DEFAULT_PATH))) + '/'

    def launch(self, auth_url, image, flavor, network, keypair, security_group='all', region=None,
               user_domain_name='Default', project_id=None, **kwargs):
        """Create the MiCADO node

        Args:
            auth_url ([type]): [description]
            image ([type]): [description]
            flavor ([type]): [description]
            network ([type]): [description]
            keypair ([type]): [description]
            security_group (str, optional): [description]. Defaults to 'all'.
            region ([type], optional): [description]. Defaults to None.
            user_domain_name (str, optional): [description]. Defaults to 'Default'.
            project_id ([type], optional): [description]. Defaults to None.

        Raises:
            MicadoException: [description]
            MicadoException: [description]
            MicadoException: [description]
            MicadoException: [description]
            MicadoException: [description]
            MicadoException: [description]

        Returns:
            MicadoInfo: Dataclass with MiCADO ID and IP
        """
        try:
            pub_key = SSHKeyHandling.get_pub_key(self.home)
            conn, conn_nova = self._get_connection(
                auth_url, region, project_id, user_domain_name)
            image = conn.get_image(image)
            flavor = conn.get_flavor(flavor)
            network = conn.get_network(network)
            keypair = conn.get_keypair(keypair)
            security_group = conn.get_security_group(security_group)
            if image is None:
                raise MicadoException("Can't find image!")
            if flavor is None:
                raise MicadoException("Can't find flavor!")
            if network is None:
                raise MicadoException("Can't find network!")
            if keypair is None:
                raise MicadoException("Can't find keypair!")
            if security_group is None:
                raise MicadoException("Can't find security_group!")
            unused_ip = self.get_unused_floating_ip(conn)
            if len(unused_ip) < 1:
                raise MicadoException("Can't find availabe floating IP!")
            ip = random.choice(unused_ip)
            logger.info('Creating VM...')
            cloud_init_config = """
            #cloud-config

            ssh_authorized_keys:
            - {}
            """.format(pub_key)
            name_id = uuid.uuid1()
            server = conn_nova.servers.create(
                'MiCADO-{}'.format(name_id.hex),
                image.id,
                flavor.id,
                security_groups=[security_group.id],
                nics=[{"net-id": network.id}],
                key_name=keypair.name,
                userdata=cloud_init_config)
            # server = conn.compute.create_server(
            #     name='MiCADO-{}'.format(name_id.hex), image_id=image.id, flavor_id=flavor.id,
            # key_name=keypair.name, userdata=cloud_init_config, timeout=300,
            # networks=[{"uuid": network.id}], security_groups=[{"name":
            # security_group.id}])
            logger.info('The VM {} starting...'.format(server.id))
            server = conn.get_server(server.id)
            logger.info('Waiting for running state, and attach {} floating ip...'.format(
                ip.floating_ip_address))
            conn.wait_for_server(server, auto_ip=False,
                                 ips=ip.floating_ip_address, timeout=600)
            self._persist_data(ip.floating_ip_address, server.id,
                               auth_url, region, project_id, user_domain_name)
            return MicadoInfo(server.id, ip.floating_ip_address)
        except MicadoException as e:
            logger.error(f"Exception cought: {e}")
            raise
        except Exception as e:
            logger.error(f"Exception cought: {e}")
            if 'server' in locals():
                conn.delete_server(server.id)
                logger.info(f"{server.id} VM dropped.")
            raise

    def delete(self, id):
        """Destroy the existing MiCADO VM.

        Args:
            id (string): The MiCADO UUID.

        Raises:
            MicadoException: Missing or incorrect data.
        """
        try:
            auth_url = None
            region_name = None
            project_id = None
            user_domain_name = None
            yaml = YAML()
            content = None
            with open(self.home + 'data.yml', mode='r') as f:
                content = yaml.load(f)
            search = [i for i in content["micados"] if i.get(id, None)]
            if not search:
                logger.debug(
                    "This {} ID can not find in the data file.".format(id))
                pass
            else:
                logger.debug("Remove {} record".format(search))
                auth_url = search[0][id]["auth_url"]
                region_name = search[0][id]["region_name"]
                project_id = search[0][id]["project_id"]
                user_domain_name = search[0][id]["user_domain_name"]
                content["micados"].remove(search[0])
                with open(self.home + 'data.yml', mode='w') as f:
                    yaml.dump(content, f)
            conn, _ = self._get_connection(
                auth_url, region_name, project_id, user_domain_name)
            if conn.get_server(id) is None:
                raise MicadoException("{} is not a valid VM ID!".format(id))
            conn.delete_server(id)
            logger.info('Dropping node {}'.format(id))
            if os.path.isfile(self.home + id + '-ssl.pem'):
                logger.info("remove {}-ssl.pem".format(self.home + id))
                os.remove(self.home + id + '-ssl.pem')
            return "Destroyed"
        except MicadoException as e:
            logger.error(f"Exception cought: {e}")

    def _get_credentials(self):
        """Read credential from file.

        Raises:
            TypeError: Missing or incorrect credential data.

        Returns:
            Authenticator: specific authenticator object
        """
        with open(self.home + "credentials-cloud-api.yml", "r") as stream:
            yaml = YAML()
            auth_data = yaml.load(stream)

        resources = {}
        for resource in auth_data["resource"]:
            resources[resource["type"]] = resource["auth_data"]

        nova = {
            key: val
            for key, val
            in resources.get("nova", {}).items()
            if val
        }

        errors = []
        for auth in AUTH_TYPES:
            try:
                return auth(**nova)
            except TypeError as error:
                errors.append(f"{auth.__name__}.{error}")

        errors = "\n" + "\n".join(errors)
        raise TypeError(f"Incomplete/ambiguous credentials: {errors}")

    def get_unused_floating_ip(self, conn):
        """Return unused ip.

        Args:
            conn ([type]): OpenStack connection

        Returns:
            dict: Unused IP
        """
        return [addr for addr in conn.list_floating_ips()
                if addr.attached == False]

    def _get_connection(
        self, auth_url, region_name, project_id, user_domain_name
    ):
        """Create OpenStack connection.

        Args:
            auth_url (string): Authentication URL for the NOVA
                resource.
            region_name (string, optional): Name of the region resource.
                Defaults to None.
            project_id (string, optional): ID of the project resource.
                Defaults to None.
            user_domain_name (string, optional): Define the user_domain_name.
                Defaults to 'Default'

        Raises:
            Exception: Project ID missing

        Returns:
            tuple: OpenStackSDK connection, and nova_client Connection
        """
        logger.info("Pulling credentials...")
        authenticator = self._get_credentials()
        authenticator.project_id = project_id
        authenticator.user_domain_name = user_domain_name
        authenticator.auth_url = auth_url

        logger.info("Authenticating with OpenStack...")
        auth = authenticator.authenticate()
        sess = session.Session(auth=auth)
        return (
            connection.Connection(
                region_name=region_name,
                session=sess,
                compute_api_version="2",
                identity_interface="public",
            ),
            nova_client.Client(2, session=sess, region_name=region_name),
        )

    def _persist_data(self, ip, server_id, auth_url,
                      region_name, project_id, user_domain_name):
        """
        """
        endpoint = f'https://{ip}/toscasubmitter'
        file_location = self.home + "data.yml"
        DataHandling.persist_data(path=file_location,
                                  server_id=server_id,
                                  ip=ip,
                                  auth_url=auth_url,
                                  region_name=region_name,
                                  project_id=project_id,
                                  user_domain_name=user_domain_name,
                                  endpoint=endpoint)
