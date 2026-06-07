"""Project exceptions."""


class ConfigError(ValueError):
    """Raised when memory configuration is missing or invalid."""


class StorageError(RuntimeError):
    """Raised when local storage cannot be used."""
