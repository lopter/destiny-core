import asyncio
import email.mime.application
import email.mime.multipart
import email.mime.text
import gzip
import logging
import os
import smtplib
import socket
import tempfile

from collections.abc import Sequence
from pathlib import Path

from clan_destiny.backups import config, utils
from .job import BackupJob

logger = logging.getLogger("backups.dump")


def _send_status_email(
    subject: str,
    exec_log: Sequence[str],
    stdout: Path | None = None,
    stderr: Path | None = None,
) -> None:
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
                    "Content-Disposition",
                    "attachment",
                    filename=mime_name,
                )
                status_email.attach(mime_logfile)
    else:
        body_parts.append("\nThe backup job could not run.")
    body_parts.append("\n-- \n{}\n".format(__file__))
    status_email.attach(
        email.mime.text.MIMEText(
            "\n".join(body_parts),
            "plain",
            "utf-8",
        )
    )
    try:
        smtpc = smtplib.SMTP("localhost")
        errs = smtpc.sendmail(from_addr, to_addr, status_email.as_string())
        assert errs == {}
        return
    except Exception as ex:
        logger.warning(f"Couldn't send email to {to_addr}: {ex}")

    logger.warning(subject)
    if len(exec_log) > 0:
        logger.warning("=== exec log ===")
        for line in exec_log:
            logger.warning(line)
        logger.warning("================")
    if stdout is not None:
        logger.warning("==== stdout ====")
        with gzip.open(stdout, "rt", encoding="utf-8") as fp:
            for line in fp:
                logger.warning(line.strip())
        logger.warning("================")
    if stderr is not None:
        logger.warning("==== stderr ====")
        with gzip.open(stderr, "rt", encoding="utf-8") as fp:
            for line in fp:
                logger.warning(line.strip())
        logger.warning("================")


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
        if not asyncio.run(utils.is_mounted(Path(job.local_path))):
            msg = f'The filesystem associated with job "{job_name}" is not mounted'
            logger.error(msg)
            subject = "{type} backup job #{name} FAILED on {host}".format(
                type=job.type.value,
                name=job_name,
                host=socket.gethostname(),
            )
            _send_status_email(
                subject=subject,
                exec_log=tuple(msg),
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
        logger.info("No backups configured")
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
