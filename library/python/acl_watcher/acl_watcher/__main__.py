from __future__ import annotations

import asyncio
import click
import collections
import functools
import logging
import pwd
import stat
import subprocess

from pathlib import Path as P
from typing import Awaitable, Callable, NamedTuple, Optional, OrderedDict

MAX_QUEUE_SIZE = 128
MAX_RECENT_FILES = 1024
MAX_PENDING_SETFACL = 64

logger = logging.getLogger("library.python.www_acl_watcher")


@click.group(help="""Use watchman to enforce permissions and ACLs when users
copy files over SMB.""")
@click.option(
    "--debug",
    default=False,
    type=click.BOOL,
    show_default=True,
    help="Enable asyncio debugging",
)
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    ctx.obj = {"debug": debug}


@main.command(
    name="www",
    help="""Users have the ability to expose static files over the web through
a personal directory.""",
)
@click.option(
    "--www-data-gid",
    default="www-data",
    show_default=True,
    help="Group ID used by the webserver.",
)
@click.option(
    "--www-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=P),  # type: ignore
    help="""
Path to the www directory of the user. Cannot be used with --username.
""",
)
@click.option(
    "--username",
    default=None,
    help="""
Compute www directory path based on the home directory of this user. Cannot
be used with --www-dir.
""",
)
@click.pass_context
def www(
    ctx: click.Context,
    www_data_gid: str,
    www_dir: Optional[P],
    username: Optional[str],
) -> None:
    if sum(1 if o else 0 for o in (www_dir, username)) != 1:
        ctx.fail("One of --www-dir or --username must be used")
    if www_dir is None:
        www_dir = P(pwd.getpwnam(username).pw_dir).parent / "www"  # type: ignore # noqa
    setfacl_handler = functools.partial(www_setfacl_handler, www_data_gid)
    coro = _watchman_loop(www_dir, setfacl_handler)
    returncode = asyncio.run(coro, debug=ctx.obj["debug"])
    ctx.exit(returncode)


@main.command(
    name="goinfre",
    help="""Goinfre is a shared mount that all users in the group
family have access to.""",
)
@click.option(
    "--family-gid",
    default="family",
    show_default=True,
    help="Group ID for the family group.",
)
@click.option(
    "--goinfre-dir",
    default=P("/stash/goinfre"),
    type=click.Path(exists=True, file_okay=False, path_type=P),  # type: ignore
    show_default=True,
    help="Path to the goinfre directory.",
)
@click.pass_context
def goinfre(ctx: click.Context, family_gid: str, goinfre_dir: P) -> None:
    setfacl_handler = functools.partial(goinfre_setfacl_handler, family_gid)
    coro = _watchman_loop(goinfre_dir, setfacl_handler)
    returncode = asyncio.run(coro, debug=ctx.obj["debug"])
    ctx.exit(returncode)


class WatchEvent(NamedTuple):
    file: P
    exists: bool
    mode: int

    @classmethod
    def from_line(cls, line: str) -> WatchEvent:
        parts = line.strip().split("\0")
        return cls(P(parts[0]), parts[1] == "True", int(parts[2]))


WatchEventQueue = asyncio.queues.Queue[Optional[WatchEvent]]


async def _watchman_loop(
    root: P,
    setfacl_handler: Callable[[P, list[WatchEvent]], Awaitable[None]],
) -> int:
    event_queue: WatchEventQueue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

    handler_coro = event_handler(root, setfacl_handler, event_queue)
    handler_task = asyncio.create_task(handler_coro)

    watchman = await asyncio.create_subprocess_exec(
        "watchman-wait",
        "--max-events", "0",
        "--null",
        "--relative", str(root),
        "--fields", "name,exists,mode",
        str(root),
        stdout=subprocess.PIPE,
    )
    while True:
        logger.info(f"waiting for watchman input")
        bytes = await watchman.stdout.readline()  # type: ignore
        if not bytes:
            logger.info(f"watchman eof")
            break
        line = bytes.decode()
        try:
            event_queue.put_nowait(WatchEvent.from_line(line))
        except asyncio.QueueFull:
            logger.error("Event queue full, giving up.")
            break
    watchman.terminate()
    await event_queue.put(None)
    _, _, returncode = await asyncio.gather(
        handler_task,
        event_queue.join(),
        watchman.wait(),
    )
    return returncode


async def event_handler(
    root: P,
    setfacl_handler: Callable[[P, list[WatchEvent]], Awaitable[None]],
    event_queue: WatchEventQueue,
) -> None:
    already_known: OrderedDict[P, None] = collections.OrderedDict()
    pending_setfacl: list[WatchEvent] = []
    while True:
        if len(pending_setfacl) > 0:
            try:
                event = event_queue.get_nowait()
            except asyncio.QueueEmpty:
                await setfacl_handler(root, pending_setfacl)
                continue
        else:
            event = await event_queue.get()

        logger.info(f"got event {event}")

        if event is None:
            event_queue.task_done()
            return
        if not event.exists:
            event_queue.task_done()
            continue
#       if event.file in already_known:
#           already_known.move_to_end(event.file)
#           event_queue.task_done()
#           continue
        if len(already_known) == MAX_RECENT_FILES:
            already_known.popitem(last=False)
        already_known[event.file] = None

        pending_setfacl.append(event)
        if stat.S_ISREG(event.mode):
            if stat.S_IMODE(event.mode) != 0o644:
                file = root / event.file
                file.chmod(0o644)
                logger.info(f"chmod 644 file {file}")
        elif stat.S_ISDIR(event.mode) and stat.S_IMODE(event.mode) != 0o755:
            # NOTE:
            #
            # We weren't actually doing this chmod in the old script,
            # also should we set some ACL on directories?
            directory = (root / event.file)
            directory.chmod(0o755)
            logger.info(f"chmod 755 directory {directory}")
        if len(pending_setfacl) == MAX_PENDING_SETFACL:
            await setfacl_handler(root, pending_setfacl)
        event_queue.task_done()


async def www_setfacl_handler(
    www_data_gid: str,
    www_dir: P,
    events: list[WatchEvent],
) -> None:
    setfacl = await asyncio.create_subprocess_exec(
        "setfacl", "-m", f"group:{www_data_gid}:r", "-", stdin=subprocess.PIPE,
    )
    paths = (f"{www_dir / event.file}\n".encode() for event in events)
    setfacl.stdin.writelines(paths)  # type: ignore
    await setfacl.stdin.drain()  # type: ignore
    logger.info(f"cleared {len(events)} pending setfacl")
    events.clear()


async def goinfre_setfacl_handler(
    family_gid: str,
    goinfre_dir: P,
    events: list[WatchEvent],
) -> None:
    acls = ("group::rw", f"group:{family_gid}:rw", "m::rw")
    cmd = ("setfacl", "-m", ",".join(acls), "-")
    setfacl = asyncio.create_subprocess_exec(*cmd, stdin=subprocess.PIPE)
    for event in events:
        path = f"{goinfre_dir / event.file}\n".encode()
        setfacl.stdin.write(path)  # type: ignore
    await setfacl.drain()  # type: ignore # noqa
    logger.info(f"cleared {len(events)} pending setfacl")
    events.clear()
