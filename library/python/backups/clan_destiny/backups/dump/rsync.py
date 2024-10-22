import shlex

from pathlib import Path
from typing import Optional


class RsyncCommands(object):

    SKIP_COMPRESS_SUFFIXES = tuple(sorted({  # sort is important for tests
        "7z", "ace", "avi", "bz2", "deb", "flac", "gpg", "gz", "iso", "jpeg",
        "jpg", "lz", "lzma", "lzo", "mkv", "mov", "mp3", "mp4", "ogg", "opus",
        "png", "rar", "rpm", "rzip", "tbz", "tgz", "tlz", "webm", "txz", "xz",
        "z", "zip",
    }))
    SKIP_COMPRESS_OPTION = "--skip-compress={}".format(
        " ".join(SKIP_COMPRESS_SUFFIXES)
    )

    def __init__(
        self,
        remote_host: str,
        local_path: Path,
        remote_path: Path,
        remote_port: Optional[int] = None,
    ):
        self.remote = remote_host
        self.local_path = local_path
        self.remote_host = remote_host
        self.remote_path = remote_path
        self.remote_port = remote_port

    def _make_base(self, identity_file: Optional[Path] = None) -> tuple[str, ...]:
        ssh_cmd = [
            "ssh",
            "-v",
            "-o BatchMode=yes",  # never ask for something on stdin
            "-o Compression=no",  # we do it beforehand
            "-o ControlMaster=no",
            "-o VisualHostKey=no",
        ]
        if identity_file is not None:
            path = shlex.quote(str(identity_file))
            ssh_cmd.append("-i {}".format(path))
        if self.remote_port:
            ssh_cmd.append("-p {:d}".format(self.remote_port))
        return (
            "rsync",
            "--archive",
            "--human-readable",
            "--numeric-ids",
            "--rsh={}".format(" ".join(ssh_cmd)),
            "--stats",
        )

    def _make_src_dst(self, direction: str) -> tuple[str, ...]:
        if direction == "pull":
            source = "{}:{}".format(self.remote_host, self.remote_path)
            return (source, str(self.local_path))
        dest = "{}:{}".format(self.remote_host, self.remote_path)
        return (str(self.local_path), dest)

    def mirror_copy(self, direction, identity_file=None):
        # type: (str, Optional[Path]) -> tuple[str, ...]
        """Get the rsync command executed on the client side."""

        mirror_options = (
            "--new-compress",
            self.SKIP_COMPRESS_OPTION,
            "--hard-links",  # preserve hard links
            "--acls",  # preserve ACLs
            "--xattrs",  # preserve extended attributes
            # NOTE: We probaby wanna make --delete an option (e.g: for incoming
            #       directories):
            "--delete",
        )
        return (
            self._make_base(identity_file) +
            mirror_options +
            self._make_src_dst(direction)
        )

    def copy(self, direction, identity_file=None):
        # type: (str, Optional[Path]) -> tuple[str, ...]
        return self._make_base(identity_file) + self._make_src_dst(direction)

    def _make_server_src_dst(self, direction):
        # type: (str) -> tuple[str, str]
        if direction == "pull":
            return (".", str(self.remote_path))
        raise NotImplementedError("FIXME")

    def server_mirror_copy(self, direction):  # (str) -> tuple[str, ...]
        """Get the rsync command executed on the server (sshd) side."""

        copy_cmd = ["rsync", "--server"]
        # The sender is the rsync process that has access to the source files
        # being synchronised, which is gonna be the server if we are doing a
        # pull. And the receiver rsync process (that has access to the
        # destination files) is responsible for the the deletion of files that
        # do not exists at the source anymore.
        copy_cmd.append("--sender" if direction == "pull" else "--delete")
        copy_cmd.extend([
            # Looks like the short options will end with .iLsfxC with more
            # recent version of rsync:
            "-lHogDtpAXrzze.iLsfxC",  # x seems to be --one-file-system
            self.SKIP_COMPRESS_OPTION,
            "--numeric-ids",
            # push: (is apparently the same as pull for those args)
            ".",
            str(self.remote_path),
        ])
        return tuple(copy_cmd)
