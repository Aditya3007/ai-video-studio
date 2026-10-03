"""Provider-neutral storage exceptions."""


class StorageError(Exception):
    """Base class for storage failures."""


class StorageNotFoundError(StorageError):
    """Requested object does not exist in storage."""


class StorageConflictError(StorageError):
    """Object already exists or a conflict occurred."""


class StorageConfigurationError(StorageError):
    """Storage backend is misconfigured or missing required dependencies."""


class StorageSecurityError(StorageError):
    """Storage operation violated a security boundary (e.g. path traversal)."""
