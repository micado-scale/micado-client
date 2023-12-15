import logging
import logging.config
import os
import paramiko
import requests
import socket
import subprocess
import time
import urllib3
from pathlib import Path
from requests.adapters import Retry, HTTPAdapter

from micado.installer.ansible.playbook import Playbook
from micado.exceptions import MicadoException
from micado.utils.utils import DataHandling, generate_password
from ruamel.yaml import YAML

DEFAULT_PATH = Path.home() / ".micado-cli"
DEFAULT_VERS = "v0.11.0"
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
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s : %(message)s")
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AnsibleInstaller:
    micado_version = os.environ.get("MICADO_VERS", DEFAULT_VERS)
    api_version = os.environ.get("API_VERS", API_VERS)
    home = str(Path(os.environ.get("MICADO_DIR", DEFAULT_PATH))) + "/"

    def deploy(
        self,
        micado,
        micado_user="admin",
        micado_password=None,
        terraform=True,
        occopus=False,
        wireguard=True,
        **kwargs,
    ):
        instance_ip = micado.ip
        micado_id = micado.id

        logger.info("Check instance availability...")
        self._check_availability(instance_ip)

        logger.info("Generating playbook inputs...")
        micado_password = micado_password or generate_password()
        hosts = self._generate_inventory(instance_ip)
        extravars = self._generate_extravars(
            micado_user, micado_password, terraform, occopus, wireguard
        )

        logger.info("Running playbook...")
        self._run_playbook(micado_id, hosts, extravars)
        self._check_submitter(instance_ip, micado_user, micado_password)
        logger.info("MiCADO deployed!")

        self._get_self_signed_cert(instance_ip, micado_id)
        self._store_data(micado_id, self.api_version, micado_user, micado_password)
        logger.info(f"MiCADO ID is: {micado_id}")
        
    def _check_submitter(self, instance_ip, user, passw):
        """Check the submitter endpoint is returning 200"""
        self._check_port_availability(instance_ip, 443)
        s = requests.Session()
        s.auth = (user, passw)
        s.verify = False
        
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.get(f"https://{instance_ip}/toscasubmitter/v2.0/applications/")

    def _check_availability(self, instance_ip):
        """Perform availability checks"""
        self._check_port_availability(instance_ip, 22)
        self._remove_know_host()
        self._get_ssh_fingerprint(instance_ip)
        self._check_ssh_availability(instance_ip)

    def _run_playbook(self, micado_id, hosts, extravars):
        """Run the playbook"""
        playbook = Playbook(self.micado_version, micado_id, self.home)
        runner = playbook.run(hosts, extravars)
        if runner.rc == 0:
            logger.info("Playbook complete.")
        else:
            msg = "\n".join([event["stdout"] for event in list(runner.events)[-5:]])
            logger.error(msg)
            raise MicadoException(msg)

    def _generate_inventory(self, ip):
        """Generate hosts info for Playbook

        Args:
            ip (string): MiCADO IP
        """
        host_dict = {}
        host_dict[
            "ansible_ssh_private_key_file"
        ] = f"{self.home}micado_cli_config_priv_key"
        host_dict["ansible_host"] = ip
        host_dict["ansible_user"] = "ubuntu"
        hosts = {"all": {"hosts": {"micado": host_dict}}}

        return hosts

    def _generate_extravars(self, micado_user, micado_password, terraform, occopus):
        """Configure ansible-micado, with credentials, etc...

        Args:
            micado_user (string): User defined MiCADO user
            micado_password (string): User defined MiCADO password
            terraform (boolean): Terraform enabled
            occopus (boolean): Occopus enabled
        """

        security_dict = self._generate_credential_data(micado_user, micado_password)

        extra_variables = {
            "cloud_cred_path": str(micado_cli_dir / "credentials-cloud-api.yml"),
            "registry_cred_path": str(micado_cli_dir / "credentials-registries.yml"),
            "enable_terraform": terraform,
            "enable_occopus": occopus,
            "enable_wireguard": wireguard,
            "security": security_dict,
        }

        return extra_variables

    def _generate_credential_data(self, micado_user, micado_password):
        """Create MiCADO credential file.

        Args:
            micado_user (string): User defined MiCADO user
            micado_password ([type]): User defined MiCADO password
        """
        logger.info("Loading MiCADO credentials...")

        auth_dict = {
            "authentication": {"username": micado_user, "password": micado_password}
        }

        micado_cred_path = micado_cli_dir / "credentials-micado.yml"
        if not micado_cred_path.is_file():
            return auth_dict

        with open(micado_cred_path, "r") as f:
            yaml = YAML()
            credential_dict = yaml.load(f)
            credential_dict.update(auth_dict)

        return credential_dict

    def _check_port_availability(self, ip, port):
        """Check the given port availability.

        Args:
            ip (string): IP address of the VM
            port (string): Port number

        Raises:
            Exception: When timeout reached
        """
        logger.info("Check {} port availability...".format(port))
        attempts = 0
        sleep_time = 2
        max_attempts = 1000
        result = None
        logger.debug(
            "IP: {} \tPort: {} \tsleeptime:{}".format(
                ip,
                port,
                sleep_time,
            )
        )
        while attempts < max_attempts and result != 0:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket.setdefaulttimeout(1)
            result = s.connect_ex((ip, port))
            s.close()
            attempts += 1
            if result == 0:
                logger.info("{} port is available...".format(port))
                break
            logger.debug(
                "attempts:{}/{} Still no answer. Try again {} seconds later...".format(
                    attempts, max_attempts, sleep_time
                )
            )
            time.sleep(sleep_time)

        if attempts == max_attempts:
            raise Exception(
                "{} second passed, and still cannot reach {}.".format(
                    attempts * sleep_time, port
                )
            )

    def _remove_know_host(self):
        """Remove known_host file"""
        known_hosts = str(Path.home()) + "/.ssh/known_hosts"
        if not os.path.isfile(known_hosts):
            return
        with open(known_hosts) as file:
            all_lines = file.readlines()
        with open(known_hosts + ".old", "a") as file2:
            file2.writelines(all_lines)
        os.remove(known_hosts)

    def _get_ssh_fingerprint(self, ip):
        """Get SSH fingerprint

        Args:
            ip (string): Target IP address
        """
        known_hosts = str(Path.home()) + "/.ssh/known_hosts"
        result = subprocess.run(
            ["ssh-keyscan", "-H", ip],
            shell=False,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        with open(known_hosts, "a") as f:
            f.writelines(result.stdout.decode())

    def _get_self_signed_cert(self, ip, id):
        """Get MiCADO self signed SSL

        Args:
            ip (string): Target IP
            id (string): UUID of the VM
        """
        logger.info("Get MiCADO self_signed cert")

        key = paramiko.RSAKey.from_private_key_file(
            f"{self.home}micado_cli_config_priv_key"
        )
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=ip, username="ubuntu", pkey=key)
        sftp = ssh.open_sftp()
        sftp.get("/var/lib/micado/zorp/config/ssl.pem", f"{self.home}{id}-ssl.pem")
        sftp.close()
        ssh.close()

    def _store_data(self, server_id, api_version, micado_user, micado_password):
        """Persist configuration specific data

        Args:
            server_id (string): UUID of the server
            api_version (string): Toscasubmitter API version
            micado_user (string): MiCADO username
            micado_password (string): MiCADO password
        """
        cert_path = f"{self.home}{server_id}-ssl.pem"
        DataHandling.update_data(
            self.home + "data.yml",
            server_id,
            api_version=api_version,
            micado_user=micado_user,
            micado_password=micado_password,
            cert_path=cert_path,
        )

    def get_api_version(self):
        """
        Return the MiCADO Submitter API version. Only v2.0 supported.

        Returns:
            string: MiCADO Submitter API version
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
            result = subprocess.run(
                [
                    "ssh",
                    "-i",
                    self.home + "micado_cli_config_priv_key",
                    "ubuntu@" + ip,
                    "ls -lah",
                ],
                shell=False,
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode == 0:
                logger.debug("SSH connection available...")
                break
            logger.debug(result.stderr.decode())
            attempts += 1
            logger.debug(
                "attempts:{}/{} Cloud-init still running. Try again {} second later".format(
                    attempts + 1, max_attempts, sleep_time
                )
            )
            time.sleep(sleep_time)

        if attempts == max_attempts:
            raise Exception(
                "{} second passed, and still cannot reach SSH.".format(
                    attempts * sleep_time
                )
            )
