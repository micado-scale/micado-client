import sys
import os
import shutil
import contextlib
from pathlib import Path

import click
import ansible_runner
from requests.exceptions import ConnectionError
from ruamel.yaml import YAML

from micado.settings import CONFIGS, DEMOS, CLOUDS, warned_vault
from micado.installer.ansible.playbook import Playbook
from micado import MicadoClient, exceptions

yaml = YAML()

DEFAULT_VERS = "v0.12.8"

class OrderedGroup(click.Group):
    def list_commands(self, ctx) -> list[str]:
        return self.commands.keys()


@click.group(cls=OrderedGroup)
@click.pass_context
def cli(ctx):
    """The MiCADO Command Line Interface.

    \b
    A typical workflow consists of:
      `micado init`    To gather setup files
      `micado config`  To configure the deployment
      `micado up`  To deploy MiCADO
    """
    home = Path(".micado").absolute()
    if ctx.invoked_subcommand == "init":
        pass
    elif not home.is_dir():
        click.secho("The current directory is not initialised. ", fg="yellow", nl=False)
        click.secho(
            "Please initalise a new directory with `micado init`. ", fg="yellow"
        )
        sys.exit(1)

@cli.command()
@click.argument(
    "ADT",
    required=True,
    type=click.Path(file_okay=True, writable=False, readable=True, resolve_path=True),
)
def start(adt):
    """Start a MiCADO app.

    Expects a YAML or CSAR ADT
    """
    client = get_client()
    click.secho(f"Starting MiCADO app...")
    try:
        with open(adt, "rb") as file_data:
            client.applications.create(app_id="MICADO-APP", file=file_data)
    except ConnectionError:
        click.secho(f"Cannot connect due to network issue.", fg="red")
        sys.exit(1)
    except exceptions.MicadoException as err:
        click.secho(f"Issue starting MiCADO app.\n{err}", fg="red")
        sys.exit(1)
    except Exception as err:
        click.secho(f"Unhandled exception starting MiCADO app.\n{err}", fg="red")
        sys.exit(1)
    click.secho(f"MiCADO app succesfully launched.", fg="green")

@cli.command()
def stop():
    """Removes the MiCADO app.
    """
    client = get_client()
    click.secho(f"Removing MiCADO app...")
    try:
        client.applications.delete(app_id="MICADO-APP")
    except ConnectionError:
        click.secho(f"Cannot connect due to network issue.", fg="red")
        sys.exit(1)
    except exceptions.MicadoException as err:
        click.secho(f"Issue stopping MiCADO app.\n{err}", fg="red")
        sys.exit(1)
    click.secho(f"MiCADO app succesfully removed.", fg="green")

@cli.command()
def info():
    """List running MiCADO app.
    """
    client = get_client()
    try:
        apps = client.applications.list()
        if apps:
            click.secho(f"Currently running: {', '.join([app.id for app in apps])}", fg="green")
        else:
            click.secho(f"No MiCADO app running.", fg="green")
    except ConnectionError:
        click.secho(f"Cannot connect due to network issue.", fg="red")
        sys.exit(1)
    except exceptions.MicadoException as err:
        click.secho(f"Issue getting info from MiCADO.\n{err}", fg="red")
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
    help="MiCADO semantic version, prefixed by v (e.g. v0.12.2)",
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

@cli.command()
@click.argument(
    "demo",
    required=True,
    type=click.Choice(DEMOS.keys(), case_sensitive=False),
)
@click.argument(
    "cloud",
    required=True,
    type=click.Choice(CLOUDS, case_sensitive=False),
)
def demo(demo, cloud):
    """Edit the Application Description Template for DEMO on CLOUD

    Provide instance configuration to host the demo and run with
    `micado start FILE`    
    """
    if demo == "cqueue" and cloud not in ["ec2", "cloudsigma"]:
        click.secho("Sorry, `cqueue` only supports ec2 and cloudsigma.")
        sys.exit(1)
    open_demo_file(demo, cloud)
    click.secho(
        f"If you are done configuring the ADT, run it with `micado start FILE`", fg="green"
    )


@cli.command()
@click.argument(
    "config",
    required=True,
    type=click.Choice(CONFIGS.keys(), case_sensitive=False),
)
def config(config):
    """Set CONFIG for a MiCADO cluster before deployment."""
    open_config_file(config)


@cli.command()
@click.option(
    "--vault",
    is_flag=True,
    help="Asks for the vault password. (Required if using vault)",
)
@click.option(
    "--update-auth",
    is_flag=True,
    help="Updates cloud and registry credentials of an existing cluster.",
)
def up(vault, update_auth):
    """Deploys a MiCADO cluster as per the configuration"""
    if not os.path.exists("".join(CONFIGS["hosts"][1:])):
        click.secho(f"MiCADO host not configured! Use `micado config hosts`", fg="red")
        sys.exit(1)
    if not os.path.exists("".join(CONFIGS["cloud"][1:])) and not os.path.exists("".join(CONFIGS["gcp"][1:])):
        click.secho(
            f"Deploying with no clouds configured. Use `micado config cloud`", fg="yellow"
        )

    password = (
        click.prompt("Enter the vault password", type=str, hide_input=True)
        if vault
        else ""
    )
    cmdline = "--ask-vault-pass " if vault else " "
    cmdline += "--tags update-auth" if update_auth else ""
    passwords = {"^Vault password:\\s*?$": password} if vault else {}

    ansible_runner.run(
        playbook="micado.yml",
        cmdline=cmdline,
        passwords=passwords,
        private_data_dir="./.micado/playbook",
    )

@cli.command()
def edge():
    """Generates edge script and registry for a running MiCADO"""
    if not os.path.exists("".join(CONFIGS["hosts"][1:])):
        click.secho(f"MiCADO must be deployed to generate edge script.", fg="red")
        sys.exit(1)

    cmdline = "--tags edge-files"

    ansible_runner.run(
        playbook="agent.yml",
        cmdline=cmdline,
        private_data_dir="./.micado/playbook",
    )


def get_client() -> MicadoClient:
    endpoint, version = get_endpoint_and_api()
    username, password = get_micado_creds()

    return MicadoClient.from_existing(
        endpoint,
        version,
        username,
        password
    )

def directory_is_not_empty(dir) -> bool:
    try:
        return bool(os.listdir(dir))
    except FileNotFoundError:
        return False

def get_actual_config_file(file) -> Path:
    *dirs, ext = file
    home = Path(".micado").absolute()
    return home.joinpath(*dirs).with_suffix(ext)

def remove_sample_from_filename(file):
    path = get_actual_config_file(file)
    try:
        src = path.parent / f"sample-{path.name}"
        dst = path.parent / f"{path.name}"
        shutil.move(src, dst)
    except FileNotFoundError:
        pass


def get_symlink_config_file(file) -> str:
    path = get_actual_config_file(file)
    try:
        Path(path.name).absolute().symlink_to(path)
    except FileNotFoundError:
        raise
    except FileExistsError:
        pass
    return str(Path(path.name).absolute())

def get_endpoint_and_api() -> tuple[str, str]:
    with open(get_actual_config_file(CONFIGS["hosts"])) as file:
        hosts = yaml.load(file)
    ip = hosts["all"]["hosts"]["micado"]["ansible_host"]

    port = 443
    try:
        with open(get_actual_config_file(CONFIGS["settings"])) as file:
            settings = yaml.load(file)
        port = settings["web_listening_port"]
    except FileNotFoundError:
        pass

    return f"https://{ip}:{port}/toscasubmitter/", "v2.0"

def get_micado_creds() -> tuple[str, str]:
    user, pwrd = "admin", "admin"
    try:
        with open(get_actual_config_file(CONFIGS["web"])) as file:
            web = yaml.load(file)
        user = web["authentication"]["username"]
        pwrd = web["authentication"]["password"]
    except FileNotFoundError:
        pass

    return user, pwrd

def produce_credential_warning(file):
    warning_file = Path(".micado").absolute() / warned_vault
    if warning_file.exists():
        return
    
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

    warning_file.touch()


def reset_directory(target):
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(Path(target) / ".micado")
        for file in CONFIGS.values():
            (Path(target) / file[1]).unlink()


def open_config_file(choice):
    file = CONFIGS[choice]
    handle_file_opening(file)
    if file[0].endswith("credentials"):
        produce_credential_warning(file)


def open_demo_file(choice, cloud):
    if cloud not in CLOUDS:
        click.secho(f"Unsupported cloud {cloud}.", fg="red")
        click.secho(f"  Supported clouds are: {', '.join(CLOUDS)}", fg="yellow")
        sys.exit(1)

    dir, name, ext = DEMOS[choice]
    file = dir, f"{name}_{cloud}", ext
    handle_file_opening(file)

def handle_file_opening(file):
    remove_sample_from_filename(file)
    try:
        symlink = get_symlink_config_file(file)
    except FileNotFoundError:
        click.secho("Could not find the file.", fg="red")
        click.secho("  Reset all files with `micado init . --force`")
        sys.exit(1)

    try:
        click.edit(filename=symlink)
    except click.UsageError:
        click.secho("Could not open default text editor.", fg="red")
        click.secho(f"  You can manually edit the file at {symlink}.")

    click.secho(f"File available at: {Path(symlink).name}\n", fg="green")
