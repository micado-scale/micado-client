#!/usr/bin/env python

import logging
import logging.config
import os
import socket
import subprocess
import tarfile
import time
import uuid
from pathlib import Path
from shutil import copyfile

import requests
from micado.utils.utils import DataHandling
from micado.exceptions import MicadoException
from ruamel.yaml import YAML


DEFAULT_PATH = Path.home() / ".micado-cli"
DEFAULT_VERS = "0.9.1-rev1"
API_VERS = "v2.0"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
micado_cli_dir = Path(os.environ.get("MICADO_DIR", DEFAULT_PATH))
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


class Ansible:
    micado_version = os.environ.get("MICADO_VERS", DEFAULT_VERS)
    api_version = os.environ.get("API_VERS", API_VERS)
    home = str(Path(os.environ.get("MICADO_DIR", DEFAULT_PATH)))+'/'
    ansible_folder = home+'ansible-micado-'+micado_version+'/'
    tarfile_location = f'{home}ansible-micado-{micado_version}.tar.gz'

    def deploy(self, server_id, micado_user='admin', micado_password='admin', terraform=False, **kwargs):
        server = DataHandling.get_properties(
            self.home+'/data.yml', server_id)
        self._download_ansible_micado()
        self._extract_tar()
        self._configure_ansible_playbook(
            server["ip"], micado_user, micado_password, terraform)
        self._check_port_availability(server["ip"], 22)
        self._remove_know_host()
        self._get_ssh_fingerprint(server["ip"])
        self._check_ssh_availability(server["ip"])
        self._deploy_micado_master()
        self._check_port_availability(server["ip"], 443)
        logger.info('MiCADO master deployed!')
        self._get_self_signed_cert(server["ip"], server_id)
        self._store_data(server_id, self.api_version,
                         micado_user, micado_password)
        logger.info(f"MiCADO master ID is: {server_id}")

    def _download_ansible_micado(self):
        """Download ansible_micado from GitHub and write down to home directory.
        """
        logger.info('Download Ansible MiCADO...')
        url = f'https://github.com/micado-scale/ansible-micado/releases/download/v{self.micado_version}/ansible-micado-{self.micado_version}.tar.gz'
        r = requests.get(url)
        with open(self.tarfile_location, 'wb') as f:
            f.write(r.content)

    def _extract_tar(self):
        """Extract tar
        """
        logger.info('Extract Ansible MiCADO...')
        tar_file = tarfile.open(self.tarfile_location)
        tar_file.extractall(self.home)
        tar_file.close()
        os.remove(self.tarfile_location)

    def _configure_ansible_playbook(self, ip, micado_user, micado_password, terraform):
        """Configure ansible-micado.

        Args:
            ip (string): MiCADO master IP
            micado_user (string): User defined MiCADO user
            micado_password ([type]): User defined MiCADO password
        """
        logger.info('Create default Ansible MiCADO configuration...')
        copyfile(self.ansible_folder+'sample-credentials-micado.yml',
                 self.ansible_folder+'credentials-micado.yml')
        copyfile(self.home+'credentials-cloud-api.yml',
                 self.ansible_folder+'credentials-cloud-api.yml')
        self._create_micado_hostfile(ip)
        self._create_micado_credential(micado_user, micado_password)
        if terraform:
            self._set_terraform_on()

    def _set_terraform_on(self):
        with open(self.ansible_folder+'micado-master.yml', 'r') as f:
            yaml = YAML()
            micado_master = yaml.load(f)
            for i in micado_master[0]['vars']:
                if i.get("enable_terraform", None) is not None:
                    i["enable_terraform"] = True
                    break
        with open(self.ansible_folder+'micado-master.yml', "w") as f:
            yaml.dump(micado_master, f)

    def _create_micado_hostfile(self, ip):
        """Create Ansible hostfile.

        Args:
            ip (string): MiCADO master IP
        """
        logger.info('Create and configure Ansible host file...')
        with open(self.ansible_folder+'sample-hosts.yml', 'r') as f:
            yaml = YAML()
            host_dict = yaml.load(f)
            host_dict["all"]["hosts"]["micado-target"]["ansible_ssh_private_key_file"] = self.home + \
                'micado_cli_config_priv_key'
            host_dict["all"]["hosts"]["micado-target"]["ansible_ssh_extra_args"] = '-o StrictHostKeyChecking=no'
            host_dict["all"]["hosts"]["micado-target"]["ansible_host"] = ip
        with open(self.ansible_folder+'hosts.yml', "w") as f:
            yaml.dump(host_dict, f)

    def _create_micado_credential(self, micado_user, micado_password):
        """Create MiCADO credential file.

        Args:
            micado_user (string): User defined MiCADO user
            micado_password ([type]): User defined MiCADO password
        """
        logger.info('Create and configure credential-micado-file...')
        with open(self.ansible_folder+'sample-credentials-micado.yml', 'r') as f:
            yaml = YAML()
            credential_dict = yaml.load(f)
            credential_dict["authentication"]["username"] = micado_user
            credential_dict["authentication"]["password"] = micado_password
        with open(self.ansible_folder+'credentials-micado.yml', "w") as f:
            yaml.dump(credential_dict, f)

    def _check_port_availability(self, ip, port):
        """Check the given port availability.

        Args:
            ip (string): IP address of the VM
            port (string): Port number

        Raises:
            Exception: When timeout reached
        """
        logger.info('Check {} port availability...'.format(port))
        attempts = 0
        sleep_time = 2
        max_attempts = 1000
        result = None
        logger.debug('IP: {} \tPort: {} \tsleeptime:{}'.format(
            ip, port, sleep_time,))
        while attempts < max_attempts and result != 0:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket.setdefaulttimeout(1)
            result = s.connect_ex((ip, port))
            s.close()
            attempts += 1
            if result == 0:
                logger.info('{} port is available...'.format(port))
                break
            logger.debug('attempts:{}/{} Still no answer. Try again {} seconds later...'.format(
                attempts, max_attempts, sleep_time))
            time.sleep(sleep_time)

        if attempts == max_attempts:
            raise Exception('{} second passed, and still cannot reach {}.'.format(
                attempts * sleep_time, port))

    def _deploy_micado_master(self):
        """Deploy MiCADO master services via ansible
        """
        logger.info('Deploy MiCADO master')
        subprocess.run(["ansible-playbook", "-i", "hosts.yml", "micado-master.yml"],
                       cwd=self.ansible_folder,
                       check=True)

    def _remove_know_host(self):
        """Remove known_host file
        """
        known_hosts = str(Path.home())+'/.ssh/known_hosts'
        if not os.path.isfile(known_hosts):
            return
        with open(known_hosts) as file:
            all_lines = file.readlines()
        with open(known_hosts+'.old', 'a') as file2:
            file2.writelines(all_lines)
        os.remove(known_hosts)

    def _get_ssh_fingerprint(self, ip):
        """Get SSH fingerprint

        Args:
            ip (string): Target IP address
        """
        known_hosts = str(Path.home())+'/.ssh/known_hosts'
        result = subprocess.run(["ssh-keyscan", "-H", ip],
                                shell=False,
                                stdin=None,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True)
        with open(known_hosts, 'a') as f:
            f.writelines(result.stdout.decode())

    def _get_self_signed_cert(self, ip, id):
        """Get MiCADO master self signed SSL

        Args:
            ip (string): Target IP
            id (string): UUID of the VM
        """
        logger.info("Get MiCADO self_signed cert")
        subprocess.run(
            [
                "scp",
                "-i",
                f"{self.home}micado_cli_config_priv_key",
                f"ubuntu@{ip}:/var/lib/micado/zorp/config/ssl.pem",
                f"{self.home}{id}-ssl.pem",
            ],
            shell=False,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def _store_data(self, server_id, api_version, micado_user, micado_password):
        """Persist configuration specific data

        Args:
            server_id (string): UUID of the server
            api_version (string): Toscasubmitter API version
            micado_user (string): MiCADO username
            micado_password (string): MiCADO password
        """
        cert_path = f"{self.home}{server_id}-ssl.pem"
        DataHandling.update_data(self.home+'data.yml', server_id, api_version=api_version,
                                 micado_user=micado_user, micado_password=micado_password, cert_path=cert_path)

    def get_api_version(self):
        """
        Return the MiCADO Master Submitter API version. Only v2.0 supported.

        Returns:
            string: MiCADO Master Submitter API version
        """

        return self.api_version

    def _check_ssh_availability(self, ip):
        """Check SSH availability

        Args:
            ip (string): Target IP

        Raises:
            Exception: When timeout reached
        """
        attempts = 0
        sleep_time = 2
        max_attempts = 100
        while attempts < max_attempts:
            result = subprocess.run(["ssh", "-i", self.home + 'micado_cli_config_priv_key', "ubuntu@" + ip, "ls -lah"],
                                    shell=False,
                                    stdin=None,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    check=False)
            if result.returncode == 0:
                logger.debug("SSH connection available...")
                break
            logger.debug(result.stderr.decode())
            attempts += 1
            logger.debug('attempts:{}/{} Cloud-init still running. Try again {} second later'.format(
                attempts+1, max_attempts, sleep_time))
            time.sleep(sleep_time)

        if attempts == max_attempts:
            raise Exception('{} second passed, and still cannot reach SSH.'.format(
                attempts * sleep_time))
