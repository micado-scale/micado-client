import logging
import logging.config
import os
import string
import secrets
from pathlib import Path

from Crypto.PublicKey import RSA
from ruamel.yaml import YAML

DEFAULT_PATH = Path.home() / ".micado-cli"

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
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s : %(message)s")
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)


class DataHandling:
    @staticmethod
    def persist_data(path, server_id, **kwargs):
        """Persist data to in a file

        Args:
            path (string): Persist file location
            server_id (string): MiCADO UUID
        """
        content = None
        data = list()
        args = dict()
        for key, value in kwargs.items():
            args[key] = value
        data.append({server_id: args})
        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        if os.path.isfile(path):
            logger.debug("Data file exist...")
            with open(path) as f:
                content = yaml.load(f)
            # Handle edge cases when the file is empty or it has syntax error
            try:
                content["micados"] += data
            except:
                content = dict()
                content["micados"] = data
        else:
            logger.debug("Data file does not exist. Creating new file...")
            content = {"micados": data}
        with open(path, "w") as f:
            yaml.dump(content, f)

    @staticmethod
    def get_properties(path, server_id):
        """Return properties from a server_id

        Args:
            path (string): File location
            server_id (string): MiCADO UUID

        Raises:
            Exception: return with exception when the uuid can't find in the file

        Returns:
            (string): server properties
        """
        yaml = YAML()
        content = None
        try:
            with open(path, mode="r") as f:
                content = yaml.load(f)
        except Exception as e:
            raise e
        search = [i for i in content["micados"] if i.get(server_id, None)]
        if not search:
            logger.error("Can't find {} record!".format(server_id))
            raise LookupError("Can't find property!")
        else:
            return search[0][server_id]

    @staticmethod
    def update_data(path, server_id, **kwargs):
        """Updata UUID properties in the file.

        Args:
            path (string): File location
            server_id (string): MiCADO UUID
        """
        content = None
        args = dict()
        for key, value in kwargs.items():
            args[key] = value
        args = {server_id: args}
        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        if os.path.isfile(path):
            logger.debug("Data file exist...")
            with open(path) as f:
                content = yaml.load(f)
            server = DataHandling.get_properties(path, server_id)
            args[server_id].update(server)
            for i in content["micados"]:
                if i.get(server_id, None) != None:
                    i.update(args)
                    logger.debug("Data updated...")
                    break
        with open(path, "w") as f:
            yaml.dump(content, f)


class SSHKeyHandling:
    @staticmethod
    def get_pub_key(home):
        """Get public config key from home location.

        Returns:
            string: Public config key
        """
        if not SSHKeyHandling._check_ssh_key_existance(home):
            SSHKeyHandling._create_ssh_keys(home)
        with open(home + "micado_cli_config_pub_key", "r") as f:
            pub_key = f.readline()
        return pub_key

    @staticmethod
    def _check_ssh_key_existance(home):
        """Check if SSH config key exist.

        Returns:
            boolean: True if it is exist
        """
        return os.path.isfile(home + "micado_cli_config_priv_key") and os.path.isfile(
            home + "micado_cli_config_pub_key"
        )

    @staticmethod
    def _create_ssh_keys(home):
        """Create SSH config key, and set the correct permission."""
        key = RSA.generate(2048)
        with open(home + "micado_cli_config_priv_key", "wb") as f:
            f.write(key.export_key(format="PEM"))
        with open(home + "micado_cli_config_pub_key", "wb") as f:
            f.write(key.public_key().export_key(format="OpenSSH"))
        os.chmod(home + "micado_cli_config_priv_key", 0o600)
        os.chmod(home + "micado_cli_config_pub_key", 0o666)

def generate_password():
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for i in range(14))
    return password
