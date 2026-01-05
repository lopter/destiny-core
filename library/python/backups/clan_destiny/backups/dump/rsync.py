import shlex

from collections.abc import Iterable
from pathlib import Path

from clan_destiny.backups import config


class RsyncCommands(object):
    def __init__(
        self,
        remote_host: str,
        local_path: str,
        remote_path: str,
        remote_port: int | None = None,
    ):
        self.remote: str = remote_host
        self.local_path: str = local_path
        self.remote_host: str = remote_host
        self.remote_path: str = remote_path
        self.remote_port: int | None = remote_port

    def _make_base(self, identity_files: Iterable[Path]) -> tuple[str, ...]:
        ssh_cmd = [
            "ssh",
            "-v",
            "-o BatchMode=yes",  # never ask for something on stdin
            "-o Compression=no",  # we do it beforehand
            "-o ControlMaster=no",
            "-o VisualHostKey=no",
        ]
        for each in identity_files:
            ssh_cmd.append(f"-i {shlex.quote(str(each))}")
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

    def _make_src_dst(self, direction: config.BackupDirection) -> tuple[str, str]:
        if direction == config.BackupDirection.PULL:
            source = "{}:{}".format(self.remote_host, self.remote_path)
            return (source, str(self.local_path))
        dest = "{}:{}".format(self.remote_host, self.remote_path)
        return (str(self.local_path), dest)

    def mirror_copy(
        self,
        direction: config.BackupDirection,
        identity_file: Path,
        certificate_file: Path,
    ) -> tuple[str, ...]:
        """Get the rsync command executed on the client side."""

        mirror_options = (
            "--new-compress",
            "--hard-links",  # preserve hard links
            "--acls",  # preserve ACLs
            "--xattrs",  # preserve extended attributes
            # NOTE: We probaby wanna make --delete an option (e.g: for incoming
            #       directories):
            "--delete",
        )
        return (
            self._make_base(identity_files=(identity_file, certificate_file))
            + mirror_options
            + self._make_src_dst(direction)
        )

    # missing server_copy function counterpart
    def copy(
        self,
        direction: config.BackupDirection,
        identity_file: Path,
        certificate_file: Path,
    ) -> tuple[str, ...]:
        return self._make_base(
            identity_files=(identity_file, certificate_file)
        ) + self._make_src_dst(direction)

    # was used in server_copy function that's missing here
    def _make_server_src_dst(
        self, direction: config.BackupDirection
    ) -> tuple[str, str]:
        if direction == config.BackupDirection.PULL:
            return (".", str(self.remote_path))
        raise NotImplementedError("FIXME")

    def server_mirror_copy(self, direction: config.BackupDirection) -> tuple[str, ...]:
        """Get the rsync command executed on the server (sshd) side."""

        copy_cmd = ["rsync", "--server"]
        # The sender is the rsync process that has access to the source files
        # being synchronised, which is gonna be the server if we are doing a
        # pull. And the receiver rsync process (that has access to the
        # destination files) is responsible for the the deletion of files that
        # do not exists at the source anymore.
        if direction == config.BackupDirection.PULL:
            copy_cmd.append("--sender")
        else:
            copy_cmd.append("--delete")
        copy_cmd.extend(
            [
                # Looks like the short options will end with .iLsfxC with more
                # recent version of rsync:
                "-lHogDtpAXrzze.iLsfxC",  # x seems to be --one-file-system
                "--numeric-ids",
                # push: (is apparently the same as pull for those args)
                ".",
                str(self.remote_path),
            ]
        )
        return tuple(copy_cmd)
