import socket
import socketserver
import systemd.daemon


class UnixStreamServer(socketserver.BaseServer):
    def __init__(self, socket_name: str, RequestHandlerClass) -> None:
        received: list[str] = []
        for fd, name in systemd.daemon.listen_fds_with_names().items():
            if name == socket_name:
                socketserver.BaseServer.__init__(self, socket_name, RequestHandlerClass)
                self.socket = socket.socket(fileno=fd)
                return
            received.append(name)
        raise ValueError(
            f"Could not find {socket_name} in the sockets "
            f"received from systemd (got `{', '.join(received)}`)"
        )

    def server_close(self):
        self.socket.close()

    def fileno(self):
        return self.socket.fileno()

    def get_request(self):
        return self.socket.accept()

    def shutdown_request(self, request):
        """Called to shutdown and close an individual request."""
        try:
            # explicitly shutdown. socket.close() merely releases the
            # socket and waits for GC to perform the actual close.
            request.shutdown(socket.SHUT_WR)
        except OSError:
            pass  # some platforms may raise ENOTCONN here
        self.close_request(request)

    def close_request(self, request):
        """Called to clean up an individual request."""
        request.close()
