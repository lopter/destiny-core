import atexit
import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import tempfile

from pathlib import Path
from typing import (
    Generator,
    Optional,
)


async def is_mounted(filepath: Path) -> bool:
    """Returns True if the filesystem where ``filepath`` resides is mounted."""

    # XXX: this only works on Linux for now:

    filepath = Path(os.path.realpath(str(filepath)))
    if not filepath.is_dir():
        filepath = filepath.parent

    fstab_cmd = ["findmnt", "--json", "--fstab"]
    fstab_proc_f = asyncio.create_subprocess_exec(
        *fstab_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    mtab_cmd = ["findmnt", "--json", "--target", str(filepath)]
    mtab_proc_f = asyncio.create_subprocess_exec(
        *mtab_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    fstab_proc = await fstab_proc_f
    mtab_proc = await mtab_proc_f
    fstab_out, fstab_err = (
        buf.decode() for buf in
        await fstab_proc.communicate()
    )
    mtab_out, mtab_err = (
        buf.decode() for buf in
        await mtab_proc.communicate()
    )
    fstab_rc = await fstab_proc.wait()
    mtab_rc = await mtab_proc.wait()
    if fstab_rc != 0 or len(fstab_err):
        raise subprocess.CalledProcessError(
            fstab_rc, fstab_cmd, fstab_out, fstab_err
        )
    if mtab_rc or len(mtab_err):
        raise subprocess.CalledProcessError(
            mtab_rc, mtab_cmd, mtab_out, mtab_err
        )

    fstab_entries = json.loads(fstab_out)["filesystems"]
    mtab_entries = json.loads(mtab_out)["filesystems"]

    file_fs = ""
    for mntent in fstab_entries:
        target = mntent["target"]
        if str(filepath).startswith(target):
            if len(target) > len(file_fs):
                file_fs = target

    return file_fs in (mntent["target"] for mntent in mtab_entries)


@contextlib.contextmanager
def make_tmp_dir(
    suffix: str = "",
    prefix: str = "tmp",
    dir: Optional[str] = None,
) -> Generator[Path, None, None]:
    tmpdir = tempfile.mkdtemp(suffix, prefix, dir)
    atexit.register(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)
