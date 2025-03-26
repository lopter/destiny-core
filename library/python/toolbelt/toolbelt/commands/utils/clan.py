import functools
import logging
import subprocess
import sys

from pathlib import Path
from typing import Any, Callable, cast


def ensure_root_directory[F: Callable[..., Any]](fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not Path("inventory.json").is_file():
            logging.error(
                "`inventory.json` not found.\n\nThis tool is meant "
                "to be called from the root of your clan repository."
            )
            sys.exit(1)
        return fn(*args, **kwargs)

    return cast(F, wrapper)


def vars_set(machine: str, items: dict[str, str]) -> None:
    for name, value in items.items():
        logging.info(f"Setting clan var {name} for {machine}")
        subprocess.run(
            ["clan", "vars", "set", machine, name],
            input=value,
            check=True,
            encoding="utf-8",
        )


def vars_get(machine: str, names: list[str]) -> dict[str, str]:
    items: dict[str, str] = {}
    for name in names:
        logging.info(f"Getting clan var {name} for {machine}")
        value = subprocess.run(
            ["clan", "vars", "get", machine, name],
            check=True,
            encoding="utf-8",
            capture_output=True,
        ).stdout.strip()
        items[name] = value
    return items
