"""metaprobe: extract title, Open Graph, Twitter Card and <meta> data from web pages."""

from importlib.metadata import PackageNotFoundError, version

from .extractor import MetadataExtractor
from .fetcher import Fetcher

try:
    __version__ = version("metaprobe")
except PackageNotFoundError:  # source checkout that has not been installed
    __version__ = "0.0.0+unknown"

__all__ = ["Fetcher", "MetadataExtractor", "__version__"]
