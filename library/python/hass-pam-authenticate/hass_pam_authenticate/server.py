import click
import functools
import logging
import pam
import time

from pathlib import Path
from xmlrpc.server import (
    SimpleXMLRPCDispatcher,
    SimpleXMLRPCRequestHandler,
)

from . import systemd

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
@click.pass_context
def server(ctx: click.Context) -> None:
    server = UnixStreamXMLRPCServer(ctx.obj.socket_name)
    server.register_introspection_functions()
    server.register_function(authenticate)
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
def authenticate(username: str, password: str) -> bool:
    authenticator = pam.PamAuthenticator()
    service = "hass-pam-authenticate"
    if authenticator.authenticate(username, password, service):
        return True
    logging.info(
        f"Authentication failed for {username}: "
        f"code={authenticator.code}, reason={authenticator.reason}"
    )
    return False
