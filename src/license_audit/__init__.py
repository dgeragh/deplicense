"""license_audit: Analyze dependency licenses with compatibility and outbound license recommendations."""

try:
    from ._version import __version__  # type: ignore[import-not-found,unused-ignore]
except ImportError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
