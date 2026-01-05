import click
import http.client
import os
import socket
import sys
import xmlrpc.client

from .types import AuthenticateResponse


@click.command()
@click.pass_context
def client(ctx: click.Context) -> None:
    username = getenv("username")
    password = getenv("password")
    client = UnixStreamXMLRPCClient(str(ctx.obj.socket_path))
    response = AuthenticateResponse(*client.authenticate(username, password))
    print(f"name = {response.real_name}")
    print("group = system-users")
    print(f"local_only = {'true' if response.local_only else 'false'}")
    sys.exit(0 if response.ok else 1)


class UnixStreamXMLRPCClient(xmlrpc.client.ServerProxy):
    def __init__(self, addr, **kwargs):
        transport = UnixStreamTransport(addr)
        super().__init__("http://", transport=transport, **kwargs)


class UnixStreamTransport(xmlrpc.client.Transport):
    def __init__(self, socket_path):
        self.socket_path = socket_path
        super().__init__()

    def make_connection(self, host):
        return UnixStreamHTTPConnection(self.socket_path)


class UnixStreamHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


def getenv(var: str) -> str:
    if value := os.environ.get(var):
        return value
    click.echo(f"Could not get the {var} from the environment", err=True)
    sys.exit(1)
