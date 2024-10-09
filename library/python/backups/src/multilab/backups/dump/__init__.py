import asyncio
import email.mime.application
import email.mime.multipart
import email.mime.text
import logging
import os
import shlex
import smtplib
import socket
import tempfile


from pathlib import Path

from multilab.backups import config, utils
from .job import BackupJob
from .rsync import RsyncCommands

logger = logging.getLogger("backups.dump")


def _send_status_email(subject, exec_log, stdout=None, stderr=None) -> None:
    status_email = email.mime.multipart.MIMEMultipart()
    status_email["From"] = status_email["To"] = from_addr = to_addr = "root"
    status_email["Subject"] = subject
    body_parts = ["Execution log:\n\n{}".format("\n".join(exec_log))]
    if stdout is not None and stderr is not None:
        for fname in (stdout, stderr):
            with open(fname, "rb") as fp:
                data = fp.read()
            if len(data) > 0:
                MIMEApp = email.mime.application.MIMEApplication
                mime_logfile = MIMEApp(data, "gzip")
                mime_name = os.path.basename(fname) + ".gz"
                mime_logfile.add_header(
                    "Content-Disposition", "attachment", filename=mime_name,
                )
                status_email.attach(mime_logfile)
    else:
        body_parts.append("\nThe backup job could not run.")
    body_parts.append("\n-- \n{}\n".format(__file__))
    status_email.attach(email.mime.text.MIMEText(
        "\n".join(body_parts), "plain", "utf-8",
    ))
    smtpc = smtplib.SMTP("localhost")
    smtpc.sendmail(from_addr, to_addr, status_email.as_string())


def run(cfg: config.Config, host_fqdn: str) -> None:
    # NOTE:
    #
    # Once we have the ability to publish private Python packages we can think
    # about moving most of what's here into its own Python 3 program and use
    # async/await to do backups to different hosts concurrently. We could also
    # support signals more easily to make sure the temporary directory is
    # cleaned if we get interrupted.
    # However that means some kind of API so that the external process can
    # consume arguments from Salt and give it a common.states.Result back. This
    # probably involves some JSON shenanigans with stdout and stdin.
    #
    # Things to consider:
    #
    # - Interrupt a backup job if it starts getting too long. Otherwise it can
    #   prevent the other jobs from running. Sometimes the network seems to
    #   stall. In the case of rsync backup jobs this will actually give the job
    #   an opportunity to complete on the next backup run. Async/Await would
    #   make it easy to implement that and there is RuntimeMaxSec in systemd as
    #   well too.

    job_count = job_total = 0
    for job_name, job in cfg.jobs_by_name.items():
        if job.local_host != host_fqdn:
            continue

        job_total += 1
        if not asyncio.run(utils.is_mounted(job.local_path)):
            msg = (
                f"The filesystem associated with job "
                f"\"{job_name}\" is not mounted"
            )
            logger.error(msg)
            subject = "{type} backup job #{name} FAILED on {host}".format(
                type=job.type.value,
                name=job_name,
                host=socket.gethostname(),
            )
            _send_status_email(
                subject=subject,
                exec_log=msg,
                stdout=None,
                stderr=None,
            )
            continue

        with utils.make_tmp_dir(suffix="backups") as tmp_dir:
            backup_job = BackupJob.from_name_and_config(job_name, cfg, tmp_dir)
            job_result = backup_job.run()
            stdout = job_result.stdout_fname
            stderr = job_result.stderr_fname
            if job_result.return_code == 0:
                subject = backup_job.subject(status="succeeded")
                job_count += 1
            else:
                subject = backup_job.subject(status="FAILED")
            _send_status_email(
                subject=subject,
                exec_log=job_result.log,
                stdout=stdout,
                stderr=stderr,
            )

    if job_total == 0:
        logger.info(f"No backups configured")
        return

    logger.info(f"{job_count}/{job_total} backup jobs ran successfully")


def setup_debug_script(
    cfg: config.Config,
    job_name: str,
    host_fqdn: str,
) -> Path:
    job = cfg.jobs_by_name.get(job_name)
    if job is None or job.local_host != host_fqdn:
        raise ValueError(f"Job {job_name} not found on this host")

    tmp_dir = Path(tempfile.mkdtemp(suffix=job_name, prefix="backups"))
    BackupJob.from_name_and_config(job_name, cfg, tmp_dir).setup_debug_script()
    return tmp_dir


def generate_root_authorized_keys(
    cfg: config.Config,
    host_aliases: tuple[str, ...],
) -> None:
    """Generate the SSH config to accept backup jobs from remote hosts.

    The generated SSH config is written to stdout. Errors are logged.

    :param host_aliases: values in this tuple are compared against `local_host`
      `remote_host` in the config. This is most likely just the FQDN, but maybe
      in the future being able to just use the hostname might be useful.
    """
    lines: list[str] = []
    for job_name, job_cfg in cfg.jobs_by_name.items():
        if job_cfg.type != config.BackupType.RSYNC:
            continue  # A job that doesn't need to edit authorized_keys.
        if job_cfg.remote_host not in host_aliases:
            continue  # This host is not the destination for this backup.

        if not job_cfg.public_key_path:
            logger.error(f"Missing public key path for backup job {job_name}")
            continue

        pub_key = job_cfg.public_key_path.read_text().strip()
        if not pub_key:
            logger.error(f"Empty public key for backup job {job_name}")
            continue

        rsync = RsyncCommands(
            remote_host=job_cfg.remote_host,
            local_path=job_cfg.local_path,
            remote_path=job_cfg.remote_path,
        )
        # XXX:
        #
        # The escaping is pretty fragile here, this happens to work because
        # shlex.quote will use single quotes. The sshd manpage only tells us
        # that quotes can be escaped with a backslash:
        lines.append(
            "restrict,command=\"multilab-backups-dump is_mounted {} && {}\" {}".format(
                shlex.quote(job_cfg.remote_path),
                " ".join(
                    shlex.quote(arg)
                    for arg in rsync.server_mirror_copy(job_cfg.direction)
                ),
                pub_key,
            )
        )
    print("\n".join(lines))

# vim: set foldmethod=marker:
