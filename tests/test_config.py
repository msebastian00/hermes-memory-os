from pathlib import Path

import pytest

from hermes_memory_os.config import ConfigError, load_config


def test_config_requires_explicit_data_path(monkeypatch):
    monkeypatch.delenv("HERMES_MEMORY_HOME", raising=False)

    with pytest.raises(ConfigError):
        load_config()


def test_config_accepts_data_dir(tmp_path):
    config = load_config(data_dir=tmp_path)

    assert config.base_dir == tmp_path
    assert config.sqlite_path == tmp_path / "db" / "memory.sqlite"


def test_config_blocks_hosted_embeddings_without_cloud_permission(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
paths:
  base_dir: /tmp/hermes-memory-test
  vault_dir: /tmp/hermes-memory-test/vault
  sqlite_path: /tmp/hermes-memory-test/db/memory.sqlite
  logs_dir: /tmp/hermes-memory-test/logs
embeddings:
  provider: openai
  base_url: https://api.openai.com/v1
privacy:
  cloud_allowed: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path=config_path)
