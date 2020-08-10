#!/usr/bin/env python

import os
import random
import socket
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from keystoneauth1 import loading, session
from keystoneauth1.identity import v3
from novaclient import client as nova_client
from ruamel.yaml import YAML

import openstack
from openstack import connection


"""
Low-level methods for handling a MiCADO cluster with Apache LibCloud
"""


class OpenStackLauncher:
    """
    For launching a MiCADO Master with Apache LibCloud
    """
    home = str(Path.home())+'/.micado-cli/'

    def launch(self, auth_url, image, flavor, network, security_group='all', keypair=None, region=None, user_domain_name='Default', project_id=None):
        """
        Create the MiCADO Master node
        """
        conn, conn_nova = self.get_connection(
            auth_url, region, project_id, user_domain_name)
        image = conn.get_image(image)
        flavor = conn.get_flavor(flavor)
        network = conn.get_network(network)
        keypair = conn.get_keypair(keypair)
        security_group = conn.get_security_group(security_group)
        unused_ip = self.get_unused_floating_ip(conn)
        if len(unused_ip) < 1:
            raise Exception("Can't find availabe floating IP!")
        ip = random.choice(unused_ip)
        print('Creating VM!')
        cloud_init_config = """
        #cloud-config

        ssh_authorized_keys:
        - {}

        runcmd:
        # MTA cloud fix
        - chage -d 2020-08-04 ubuntu
        """
        name_id = uuid.uuid1()
        server = conn_nova.servers.create('MiCADO-Master-{}'.format(name_id.hex), image.id, flavor.id, security_groups=[
            security_group.id], nincs=network.id, key_name=keypair.name, userdata=cloud_init_config)
        # server = conn.compute.create_server(
        #     name='MiCADO-Master-{}'.format(name_id.hex), image_id=image.id, flavor_id=flavor.id,
        #     key_name=keypair.name, userdata=cloud_init_config, timeout=300, networks=[{"uuid": network.id}], security_groups=[{"name": security_group.id}])
        print('The VM {} starting...'.format(server.id))
        server = conn.get_server(server.id)
        print('Waiting for running state, and attach {} floating ip'.format(
            ip.floating_ip_address))
        conn.wait_for_server(server, auto_ip=False,
                             ips=ip.floating_ip_address, timeout=600)

    def get_api_endpoint(self):
        """
        Return the MiCADO Master Submitter API endpoint
        """
        # TODO: Do it properly
        # /toscasubmitter/v1.0/
        return "http://submitter:5050"

    def get_api_version(self):
        """
        Return the MiCADO Master Submitter API version
        """
        return "v1.0"

    def delete(self, id, auth_url, region=None, user_domain_name='Default', project_id=None):
        """
        Destroy the MiCADO Master node
        """
        conn, _ = self.get_connection(
            auth_url, region, project_id, user_domain_name)
        if conn.get_server(id) is None:
            raise Exception("{} is not a valid VM ID!".format(id))
        conn.delete_server(id)
        print('Dropping node {}'.format(id))
        return "Destroyed"

    def get_credentials(self):
        with open(self.home+'auth_data.yml', 'r') as stream:
            yaml = YAML()
            code = yaml.load(stream)
        for iii in code['resource']:
            if iii['type'] == 'nova':
                auth_data = iii['auth_data']
                break
        # TODO: Fix error handling exception
        # if not auth_data or not 'username' in auth_data or not 'password' in auth_data:
        #     raise Exception(
        #         'Creadentials not found for NOVA api... Please use the template file')
        return auth_data

    def get_unused_floating_ip(self, conn):
        return [addr for addr in conn.list_floating_ips() if addr.attached == False]

    def get_connection(self, auth_url, region, project_id, user_domain_name):
        auth_data = self.get_credentials()
        if auth_data.get('type', None) is None:
            if project_id is None:
                raise Exception('Project ID is missing!')
            user = auth_data['username']
            password = auth_data['password']
            auth = v3.Password(auth_url=auth_url, username=user, password=password,
                               user_domain_name=user_domain_name, project_id=project_id)
        elif auth_data.get('type', None) == 'application_credential':
            app_cred_id = auth_data['id']
            app_cred_secret = auth_data['secret']
            auth = v3.ApplicationCredential(
                auth_url, application_credential_id=app_cred_id, application_credential_secret=app_cred_secret)
        else:
            raise Exception('Not a valid type')
        sess = session.Session(auth=auth)
        return connection.Connection(
            region_name=region,
            session=sess,
            compute_api_version='2',
            identity_interface='public'), nova_client.Client(2, session=sess, region_name=region)
