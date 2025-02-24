from pathlib import Path
from typing import NamedTuple


class MainOptions(NamedTuple):
    socket_name: str
    socket_path: Path
