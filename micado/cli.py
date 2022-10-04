import sys
import os
import shutil
import contextlib
from pathlib import Path
from typing import Collection

import click
import ansible_runner

from micado.installer.ansible.playbook import Playbook

DEFAULT_VERS = "v0.11.2"

CONFIGS: dict = {
    "hosts": ("playbook/inventory", "hosts.yml"),
    "cloud": ("playbook/project/credentials", "credentials-cloud-api.yml"),
    "registry": ("playbook/project/credentials", "credentials-docker-registry.yml"),
    "micado": ("playbook/project/credentials", "credentials-micado.yml"),
    "settings": ("playbook/project/host_vars", "micado.yml"),
}


class OrderedGroup(click.Group):
    def list_commands(self, ctx) -> Collection:
        return self.commands.keys()


@click.group(cls=OrderedGroup)
@click.pass_context
def cli(ctx):
    """The MiCADO Command Line Interface.

    \b
    A typical workflow consists of:
      `micado init`    To gather setup files
      `micado config`  To configure the deployment
      `micado deploy`  To install MiCADO
    """
    if ctx.invoked_subcommand == "init":
        pass
    elif not Path(".micado").absolute().is_dir():
        click.secho("The current directory is not initialised. ", fg="yellow", nl=False)
        click.secho(
            "Please initalise a new directory with `micado init`. ", fg="yellow"
        )
        sys.exit(1)


@cli.command()
@click.argument(
    "target",
    required=False,
    default=".",
    type=click.Path(file_okay=False, writable=True, readable=True, resolve_path=True),
)
@click.option(
    "--version",
    required=False,
    default=DEFAULT_VERS,
    type=str,
    help="MiCADO semantic version, prefixed by v (e.g. v0.11.2)",
)
@click.option(
    "--force",
    is_flag=True,
    help="""Reset the MiCADO setup directory. 
    WARNING: This will reset any MiCADO settings from this directory.""",
)
def init(target, version, force):
    """Initalises a TARGET directory with VERSION setup files

    Uses current directory if no TARGET, current MiCADO if no VERSION
    """
    target_text = click.style(f"{target}", italic=True, fg="reset")
    if force:
        reset_directory(target)

    elif directory_is_not_empty(target):
        click.secho(f"The directory {target_text}", fg="yellow", nl=False)
        click.secho(" is not empty. Is MiCADO already initialised?", fg="yellow")
        sys.exit(1)

    os.makedirs(target, exist_ok=True)

    playbook = Playbook(version, f"{os.getlogin()}-cli", f"{target}/")
    playbook.playbook_path = f"{target}/.micado"
    try:
        playbook.download()
    except TypeError:
        click.secho(f"Cannot find MiCADO version {version}", fg="red")
        sys.exit(1)
    playbook.extract()

    click.secho(
        f"Succesfully initialised the MiCADO setup in {target_text}", fg="green"
    )


@cli.group()
def config():
    """Configure details of a MiCADO cluster before deployment."""
    pass


@config.command()
def hosts():
    """Specify connection details for the MiCADO host (REQUIRED)"""
    open_config_file("hosts")


@config.command()
def cloud():
    """Specify cloud API credentials (REQUIRED)"""
    open_config_file("cloud")


@config.command()
def registry():
    """Specify private Docker registry credentials"""
    open_config_file("registry")


@config.command()
def micado():
    """Configure MiCADO WebUI access settings"""
    open_config_file("micado")


@config.command()
def settings():
    """Configure common deployment settings"""
    open_config_file("settings")


@cli.command()
@click.option(
    "--vault",
    is_flag=True,
    help="Asks for the vault password. (Required if using vault)",
)
def deploy(vault):
    """Deploys a MiCADO cluster as per the configuration"""
    if not os.path.exists(CONFIGS["hosts"][1]):
        click.secho(f"MiCADO host not configured! Use `micado config hosts`", fg="red")
        sys.exit(1)
    if not os.path.exists(CONFIGS["cloud"][1]):
        click.secho(
            f"Target clouds not configured! Use `micado config cloud`", fg="red"
        )
        sys.exit(1)

    password = (
        click.prompt("Enter the vault password", type=str, hide_input=True)
        if vault
        else ""
    )
    cmdline = "--ask-vault-pass" if vault else " "
    passwords = {"^Vault password:\\s*?$": password} if vault else {}

    ansible_runner.run(
        playbook="micado.yml",
        cmdline=cmdline,
        passwords=passwords,
        private_data_dir="./.micado/playbook",
    )


def directory_is_not_empty(dir) -> bool:
    try:
        return bool(os.listdir(dir))
    except FileNotFoundError:
        return False


def remove_sample_from_filename(file):
    path = Path(".micado").absolute() / Path(file[0]) / Path(file[1])
    try:
        src = path.parent / f"sample-{path.name}"
        dst = path.parent / f"{path.name}"
        shutil.move(src, dst)
    except FileNotFoundError:
        pass


def get_symlink_config_file(file) -> str:
    path = Path(".micado").absolute() / Path(file[0]) / Path(file[1])
    try:
        Path(path.name).absolute().symlink_to(path)
    except FileNotFoundError:
        raise
    except FileExistsError:
        pass
    return str(Path(path.name).absolute())


def produce_credential_warning(file):
    click.secho(
        "Please consider encrypting credential files with ansible-vault.", bold=True
    )
    click.echo("Use the same vault password across all files in this setup.\n")
    click.echo(
        "If you have ansible-vault installed, you may use the following command:"
    )
    click.secho(f"    ansible-vault encrypt {file[1]}\n", italic=True)
    click.echo("If you need to edit the file again, first decrypt it with:")
    click.secho(f"    ansible-vault decrypt {file[1]}", italic=True)


def reset_directory(target):
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(Path(target) / ".micado")
        for file in CONFIGS.values():
            (Path(target) / file[1]).unlink()


def open_config_file(choice):
    file: tuple[str, str] = CONFIGS[choice]
    remove_sample_from_filename(file)
    try:
        symlink = get_symlink_config_file(file)
    except FileNotFoundError:
        click.secho("Could not find the config file.", fg="red")
        click.secho("  Reset all files with `micado init . --force`")
        sys.exit(1)

    try:
        click.edit(filename=symlink)
    except click.UsageError:
        click.secho("Could not open default text editor.", fg="red")
        click.secho("  You can manually edit the file at {symlink}.")

    click.secho(f"Symlink created at: {symlink}\n", fg="green")
    if file[0].endswith("credentials"):
        produce_credential_warning(file)
