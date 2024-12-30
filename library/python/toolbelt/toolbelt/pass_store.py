import logging
import subprocess


def show(path: str) -> str:
    logging.info(f"Getting {path} from pass")
    return subprocess.run(
        ["pass", "show", path],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()


def set(path: str, value: str) -> None:
    logging.info(f"Setting {path} in pass")
    subprocess.run(
        ["pass", "insert", "--force", "--multiline", path],
        input=value,
        check=True,
        encoding="utf-8",
    )
