# Developing Hermes Memory OS

This project is standalone. It can be developed directly from this repository, by Codex, or from a Hermes development workspace.

## Direct Or Codex Development

From the repository root:

```bash
export PYTHONPATH=src
export HERMES_MEMORY_HOME=/tmp/hermes-memory-os-dev
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli provider-smoke
```

## Hermes Workspace Development

From a Hermes development environment, install this project in editable mode:

```bash
pip install -e /path/to/hermes-memory-os
```

Or run from source by adding this repo's `src` directory to `PYTHONPATH`.

Set runtime storage independently:

```bash
export HERMES_MEMORY_HOME=/path/to/memory-data
```

## Hermes Import Path

Hermes should load the provider through one of these stable paths:

```text
hermes_memory_os.hermes_plugin:create_provider
hermes_memory_os.hermes_plugin:load
hermes_memory_os.provider:HermesMemoryOSProvider
```

The root `hermes-plugin.yaml` records these paths for plugin loaders that use manifests. This does not make Hermes the owner of the project; it only exposes a stable integration point.

## Runtime Data

Do not store runtime memory data in the Hermes repo or in this repo. Set `HERMES_MEMORY_HOME` per machine:

- WSL2 Alienware: choose a local dev path.
- DGX Spark: choose the mounted production memory volume.
- CI/tests: use `/tmp/...`.

## Boundary

Hermes calls the provider adapter. Reachy calls Hermes/the memory API. Neither Hermes nor Reachy writes directly to SQLite, Qdrant, or wiki-brain files.
