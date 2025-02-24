import click
import functools
import grp
import logging
import os
import pexpect
import pwd
import socketserver
import sys
import time

from pathlib import Path
from xmlrpc.server import (
    SimpleXMLRPCDispatcher,
    SimpleXMLRPCRequestHandler,
)

logger = logging.getLogger("server")


class UnixStreamXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    def address_string(self):
        return self.client_address


class UnixStreamXMLRPCServer(
    socketserver.UnixStreamServer,
    SimpleXMLRPCDispatcher
):
    def __init__(
        self,
        addr,
        log_requests=True,
        allow_none=True,
        encoding=None,
        bind_and_activate=True,
        use_builtin_types=True,
    ):
        self.logRequests = log_requests
        SimpleXMLRPCDispatcher.__init__(
            self, allow_none, encoding, use_builtin_types
        )
        if os.path.exists(addr):
            os.unlink(addr)
        socketserver.UnixStreamServer.__init__(
            self,
            addr,
            UnixStreamXMLRPCRequestHandler,
            bind_and_activate,
        )
        uid = pwd.getpwnam("hass-pam-authenticate").pw_uid
        gid = grp.getgrnam("hass").gr_gid
        os.chown(addr, uid, gid)
        os.chmod(addr, 0o660)


@click.command()
@click.pass_context
def server(ctx: click.Context) -> None:
    server = UnixStreamXMLRPCServer(ctx.obj.socket_path)
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
    true_bin = pexpect.which("true")
    if not true_bin:
        click.echo("Could not find `true` in `PATH`", err=True)
        sys.exit(1)

    su_bin = "/run/wrappers/bin/su"
    if not Path(su_bin).exists():
        click.echo(f"Could not find `su` at `{su_bin}`", err=True)
        sys.exit(1)

    su = pexpect.spawn(su_bin, ["-s", true_bin, username])
    su.expect("Password:")
    su.sendline(password)
    su.wait()
    su.close()

    return su.exitstatus == 0
