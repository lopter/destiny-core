import base64
import struct

from pathlib import Path


class InvalidAuthInfo(Exception):
    pass


def parse(file: Path) -> str:
    """Extract the EDDSA public key from an SSH certificate in auth info.

    The certificate format is defined in draft-miller-ssh-cert-06 section 2.1.4.
    """
    match file.read_text().strip().split(" "):
        case ("publickey", "ssh-ed25519-cert-v01@openssh.com", certificate):
            pass
        case parts:
            raise InvalidAuthInfo(
                f"Expected an Ed25519 certificate in "
                f"`SSH_USER_AUTH` got: {parts[:2]}"
            )

    try:
        data = base64.b64decode(certificate)
    except Exception as e:
        reason = f"`SSH_USER_AUTH` is not valid base64: {e}"
        raise InvalidAuthInfo(reason) from e

    offset = 0

    # Field 1: certificate type
    cert_type, offset = read_string(data, offset)
    expected_type = b"ssh-ed25519-cert-v01@openssh.com"
    if cert_type != expected_type:
        raise InvalidAuthInfo(
            f"Expected {expected_type!r} certificate in "
            f"`SSH_USER_AUTH`, got {cert_type!r}"
        )

    # Field 2: nonce (skip it)
    _, offset = read_string(data, offset)

    # Field 3: pk (the public key we want)
    pk, _ = read_string(data, offset)
    if len(pk) != 32:
        raise InvalidAuthInfo(
            f"Expected 32-byte Ed25519 public key in "
            f"`SSH_USER_AUTH`, got {len(pk)} bytes"
        )

    # Wrap pk in SSH wire format (RFC 4253 section 6.6) for easy comparison
    # with .pub files: string "ssh-ed25519" + string pk
    key_type = b"ssh-ed25519"
    wire_format = struct.pack(">I", len(key_type)) + key_type
    wire_format += struct.pack(">I", len(pk)) + pk
    return base64.b64encode(wire_format).decode("ascii")


def read_string(data: bytes, offset: int) -> tuple[bytes, int]:
    """Read an SSH string (RFC 4251 section 5) from data at offset.

    Returns the string value and the new offset after the string.
    """
    if offset + 4 > len(data):
        raise InvalidAuthInfo(
            f"Invalid `SSH_USER_AUTH`: expected 4 bytes for string length "
            f"at offset {offset}, got {len(data) - offset}"
        )
    (length,) = struct.unpack_from(">I", data, offset)
    offset += 4
    if offset + length > len(data):
        raise InvalidAuthInfo(
            f"`Invalid `SSH_USER_AUTH`: expected {length} bytes for string "
            f"at offset {offset}, got {len(data) - offset}"
        )
    return data[offset : offset + length], offset + length
