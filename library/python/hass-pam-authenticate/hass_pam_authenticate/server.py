import click
import functools
import logging
from hass_pam_authenticate.types import AuthenticateResponse
import pam
import pwd
import time

from typing import Iterable
from xmlrpc.server import (
    SimpleXMLRPCDispatcher,
    SimpleXMLRPCRequestHandler,
)

from . import systemd
from .types import AuthenticateResponse

logger = logging.getLogger("server")


class UnixStreamXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    disable_nagle_algorithm = False  # Non-applicable to Unix sockets.

    def address_string(self):
        return self.client_address


class UnixStreamXMLRPCServer(systemd.UnixStreamServer, SimpleXMLRPCDispatcher):

    def __init__(
        self,
        socket_name: str,
        log_requests: bool = True,
        allow_none: bool = True,
        encoding: str | None =None,
        use_builtin_types: bool = True,
    ) -> None:
        self.logRequests = log_requests
        SimpleXMLRPCDispatcher.__init__(
            self, allow_none, encoding, use_builtin_types
        )
        systemd.UnixStreamServer.__init__(
            self, socket_name, UnixStreamXMLRPCRequestHandler,
        )


@click.command()
@click.option(
    "--remote-user",
    help="Do not set `local_only` for this user",
    multiple=True,
)
@click.pass_context
def server(ctx: click.Context, remote_user: list[str]) -> None:
    server = UnixStreamXMLRPCServer(ctx.obj.socket_name)
    server.register_introspection_functions()
    wrapper = functools.partial(authenticate, remote_user)
    server.register_function(functools.update_wrapper(wrapper, authenticate))
    server.serve_forever()


def rate_limit(fn):
    call_times = []

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        now = time.monotonic()
        # Remove calls older than 60 seconds
        while call_times and now - call_times[0] > 60:
            call_times.pop(0)
        if len(call_times) >= 4:
            msg = f"Called {call_times} in the past minute, sleeping for 5s"
            logger.warning(msg)
            time.sleep(5)
        call_times.append(now)
        return fn(*args, **kwargs)

    return wrapper


@rate_limit
def authenticate(
    remote_users: Iterable[str],
    username: str,
    password: str,
) -> tuple[bool, str, bool]:
    authenticator = pam.PamAuthenticator()
    service = "hass-pam-authenticate"
    if authenticator.authenticate(username, password, service):
        response = AuthenticateResponse(
            ok=True,
            real_name=pwd.getpwnam(username).pw_gecos,
            local_only=username not in remote_users,
        )
    else:
        response = AuthenticateResponse(ok=False, real_name="", local_only=False)
        logging.info(
            f"Authentication failed for {username}: "
            f"code={authenticator.code}, reason={authenticator.reason}"
        )
    return tuple(response)
