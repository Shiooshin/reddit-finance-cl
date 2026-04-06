"""main — top-level package."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("main")
except PackageNotFoundError:
    __version__ = "0.0.0"
