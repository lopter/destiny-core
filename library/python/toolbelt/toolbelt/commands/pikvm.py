import click
import tempfile

from . import utils


@click.group(
    help=f"Execute pivkm related actions",
)
def pikvm() -> None:
    pass


# Unfortunately it looks like you can use the PiKVM API to
# execute a macro script. See: https://docs.pikvm.org/api/
@pikvm.command(
    name="reboot-wintermute",
    help="Access my helper script to reboot my computer using its KVM",
)
@utils.pass_store.pass_name_option(
    default="fr/kalessin/machines/wks-sfo-wintermute/pikvm-script-reboot.json",
    help="Name of the JSON file in pass with the PiKVM reboot script",
)
def reboot_wintermute(pass_name: str) -> None:
    script = utils.pass_store.show(pass_name)
    with tempfile.NamedTemporaryFile("w+b", delete_on_close=False) as fp:
        fp.write(script.encode("utf-8"))
        click.prompt(
            f"Script written at {fp.name}, "
            f"hit return once uploaded to the PiKVM"
        )
