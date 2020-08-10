#!/usr/bin/env python

import os
import random
import socket
import subprocess
import tarfile
import time
import uuid
from pathlib import Path
from shutil import copyfile

import openstack
import requests
from Crypto.PublicKey import ECC
from keystoneauth1 import loading, session
from keystoneauth1.identity import v3
from novaclient import client as nova_client
from openstack import connection
from ruamel.yaml import YAML


"""
Low-level methods for handling a MiCADO cluster with Apache LibCloud
"""


class NovaCloudLauncher:
    """
    For launching a MiCADO Master with Apache LibCloud
    """
    home = str(Path.home())+'/.micado-cli/'
    micado_version = '0.9.0'
    ansible_folder = home+'ansible-micado-'+micado_version+'/'

    def launch(self, auth_url, image, flavor, network, security_group='all', keypair=None, region=None, user_domain_name='Default', project_id=None):
        """
        Create the MiCADO Master node
        """
        if not self._check_home_folder():
            os.mkdir(self.home)
        pub_key = self._get_pub_key()
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
        """.format(pub_key)
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
        self._download_ansible_micado()
        self._extract_tar()
        self._configure_ansible_playbook(ip.floating_ip_address)
        self._check_port_availability(ip.floating_ip_address, 22)
        self._deploy_micado_master()
        self._check_port_availability(ip.floating_ip_address, 443)
        print('MiCADO deployed!')

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
        # TODO: FIx this exception
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

    def _check_home_folder(self):
        return os.path.isdir(self.home)

    def _check_ssh_key_existance(self):
        return os.path.isfile(self.home + 'micado_cli_config_priv_key') and os.path.isfile(self.home + 'micado_cli_config_pub_key')

    def _get_pub_key(self):
        if not self._check_ssh_key_existance():
            self._create_ssh_keys()
        with open(self.home + 'micado_cli_config_pub_key', 'r') as f:
            pub_key = f.readlines()
        return pub_key

    def _create_ssh_keys(self):
        key = ECC.generate(curve='P-521')
        with open(self.home + 'micado_cli_config_priv_key', 'wt') as f:
            f.write(key.export_key(format='PEM'))
        with open(self.home + 'micado_cli_config_pub_key', 'wt') as f:
            f.write(key.public_key().export_key(format='OpenSSH'))
        os.chmod(self.home + 'micado_cli_config_priv_key', 0o600)
        os.chmod(self.home + 'micado_cli_config_pub_key',  0o666)

    def _download_ansible_micado(self):
        print('Download Ansible MiCADO')
        url = 'https://github.com/micado-scale/ansible-micado/releases/download/v' + \
            self.micado_version+'/ansible-micado-'+self.micado_version+'.tar.gz'
        r = requests.get(url)
        tarfile_location = self.home+'ansible-micado-'+self.micado_version+'.tar.gz'
        with open(tarfile_location, 'wb') as f:
            f.write(r.content)

    def _extract_tar(self):
        print('Extract Ansible MiCADO')
        tarfile_location = self.home+'ansible-micado-'+self.micado_version+'.tar.gz'
        tar_file = tarfile.open(tarfile_location)
        tar_file.extractall(self.home)
        tar_file.close()
        os.remove(tarfile_location)

    def _configure_ansible_playbook(self, ip):
        print('Copy ansible sample files')
        copyfile(self.ansible_folder+'sample-hosts.yml',
                 self.ansible_folder+'hosts.yml')
        copyfile(self.ansible_folder+'sample-credentials-micado.yml',
                 self.ansible_folder+'credentials-micado.yml')
        copyfile(self.home+'auth_data.yml',
                 self.ansible_folder+'credentials-cloud-api.yml')
        self._change_ansible_config(ip)

    def _change_ansible_config(self, ip):
        print('Extend ansible config file')
        with open(self.ansible_folder+'hosts.yml', 'r') as f:
            yaml = YAML()
            host_dict = yaml.load(f)
            host_dict["all"]["hosts"]["micado-target"]["ansible_ssh_private_key_file"] = self.home + \
                'micado_cli_config_priv_key'
            host_dict["all"]["hosts"]["micado-target"]["ansible_ssh_extra_args"] = '-o StrictHostKeyChecking=no'
            host_dict["all"]["hosts"]["micado-target"]["ansible_host"] = ip
            print()
        with open(self.ansible_folder+'hosts.yml', "w") as f:
            yaml.dump(host_dict, f)

    def _check_port_availability(self, ip, port):
        print('Check {} port availability'.format(port))
        target = ip
        attempts = 0
        sleep_time = 2
        max_attempts = 1000
        result = None
        print('IP: {} \tPort: {} \tsleeptime:{}'.format(ip, port, sleep_time,))
        while attempts < max_attempts and result != 0:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket.setdefaulttimeout(1)
            result = s.connect_ex((target, port))
            s.close()
            attempts += 1
            time.sleep(sleep_time)
            print('attempts:{}/{} Still no answer. Try again {} second later'.format(
                attempts, max_attempts, sleep_time))
        if attempts == max_attempts:
            raise Exception('{} second passed, and still cannot reach {}.'.format(
                attempts * sleep_time, port))
        else:
            print('{} port is available.'.format(port))

    # def _get_ssh_fingerprint(self, ip):
    #     print('Get ssh fingerprint')
    #     subprocess.run(["ssh-keyscan", "-H", ip, ">>", "~/.ssh/known_hosts"])

    def _deploy_micado_master(self):
        print('Deploy MiCADO master')
        time.sleep(100)
        subprocess.run(["ansible-playbook", "-i", "hosts.yml",
                        "micado-master.yml"], cwd=self.ansible_folder)

    def get_ssh_key_path(self):
        if self._check_ssh_key_existance():
            return "You can find the configuration keys under ~/.micado-cli/micado_cli_config_priv_key and ~/.micado-cli/micado_cli_config_pub_key"
        else:
            return "The key is not generated yet. Deploy the VM first"
