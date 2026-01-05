import json
import pydantic
import pytest

from pathlib import Path

from clan_destiny.backups import config


FAKE_RESTIC_B2_KEY_ID = "test-key-id"
FAKE_RESTIC_B2_APPLICATION_KEY = "test-application-key"

B2_JOBS_CONFIG = Path(__file__).parent / "b2_jobs_config.json"


@pytest.fixture
def valid_b2_jobs_config(tmp_path: Path) -> Path:
    with Path(B2_JOBS_CONFIG).open("rb") as fp:
        cfg = json.load(fp)

    # Set values that should pass config validation

    cache_dir = tmp_path / "cache_dir"
    cache_dir.mkdir(mode=0o700)

    key_id = tmp_path / "key_id"
    contents = f"{FAKE_RESTIC_B2_KEY_ID}\n"
    assert key_id.write_text(contents) > 0

    app_key = tmp_path / "app_key"
    contents = f"{FAKE_RESTIC_B2_APPLICATION_KEY}\n"
    assert app_key.write_text(contents) > 0

    cfg["restic"]["cacheDir"] = str(cache_dir)
    cfg["restic"]["b2"]["keyIdPath"] = str(key_id)
    cfg["restic"]["b2"]["applicationKeyPath"] = str(app_key)

    for job in cfg["jobsByName"]:
        password = tmp_path / f"{job}-password"
        assert password.write_text("test-password\n") > 0
        cfg["jobsByName"][job]["passwordPath"] = str(password)

    test_config = tmp_path / "b2_jobs_config.json"
    with test_config.open("w") as fp:
        json.dump(cfg, fp)

    return test_config


def test_valid_b2_jobs(valid_b2_jobs_config: Path) -> None:
    cfg = config.load(valid_b2_jobs_config)
    assert sorted(cfg.jobs_by_name.keys()) == [
        "certbot_on_b2",
        "gitolite_homedir_on_b2",
        "vault_snapshots_on_b2",
    ]
    assert cfg.restic.b2.key_id == FAKE_RESTIC_B2_KEY_ID
    assert cfg.restic.b2.application_key == FAKE_RESTIC_B2_APPLICATION_KEY


def test_invalid_b2_jobs() -> None:
    with pytest.raises(pydantic.ValidationError):
        # The raw config contains paths that don't exist:
        _ = config.load(B2_JOBS_CONFIG)
