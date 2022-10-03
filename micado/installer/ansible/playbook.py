import os
import shutil
import tarfile
from pathlib import Path

import ansible_runner
import requests

PLAYBOOK_NAME = "micado.yml"
PLAYBOOK_INTERNAL = "playbook"
ROTATION = 100  # max number of artifacts (logs, etc...) to keep
QUIET = True  # hide ansible output


class Playbook:
    def __init__(self, version: str, id: str, home_dir: str):
        self.version: str = version
        self.id: str = id
        self.tar_download: Path = Path(f"{home_dir}micado-{version}.tar.gz")
        self.playbook_path: Path = Path(f"{home_dir}micado-{version}")

    def run(self, hosts: dict, extravars: dict, playbook: str = None):
        """Run the playbook"""
        if not self.playbook_exists():
            self.download()
            self.extract()
        
        data_dir = self.playbook_path / PLAYBOOK_INTERNAL

        # fix_hosts_permissions() because https://github.com/ansible/ansible-runner/issues/853
        fix_hosts_permissions(data_dir)
        runner = ansible_runner.interface.run(
            ident=self.id,
            playbook=playbook or PLAYBOOK_NAME,
            private_data_dir=str(data_dir),
            inventory=hosts,
            extravars=extravars,
            rotate_artifacts=ROTATION,
            quiet=QUIET,
        )
        fix_hosts_permissions(data_dir)
        return runner

    def download(self):
        """Download playbook from GitHub and write down to home directory."""
        url = f"https://github.com/micado-scale/ansible-micado/tarball/{self.version}"
        r = requests.get(url, stream=True)

        with open(self.tar_download, "wb") as f:
            f.write(r.content)

        if not tarfile.is_tarfile(self.tar_download):
            os.remove(self.tar_download)
            raise TypeError(f"Download failed - check MiCADO {self.version} exists.")

    def extract(self):
        """Extract tar to the directory where it was downloaded"""
        if not os.path.isfile(self.tar_download):
            raise FileNotFoundError("Playbook tarball not found. Cannot extract.")

        tar_file = tarfile.open(self.tar_download)
        tar_path = self.tar_download.parent / tar_file.firstmember.name
        tar_file.extractall(self.tar_download.parent)
        tar_file.close()

        # Don't overwrite an existing playbook of the same version
        try:
            tar_path.rename(self.playbook_path)
        except OSError:
            shutil.rmtree(str(tar_path))

        self.tar_download.unlink()  # delete the tarball

    def remove(self):
        """Remove the playbook directory"""
        if not self.playbook_path:
            raise FileNotFoundError("Playbook directory not found. Cannot remove.")
        shutil.rmtree(str(self.playbook_path))
        self.playbook_path = None

    def playbook_exists(self):
        """Check if playbook directory exists"""
        return os.path.isdir(self.playbook_path)

def fix_hosts_permissions(path: Path):
    try:
        os.chmod(path / "inventory/hosts.json", 0o600)
    except FileNotFoundError:
        pass