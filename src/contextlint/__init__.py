"""contextlint — report when the files your agent trusts no longer match the repo."""

from .check import Finding, Report, check_file, find_context_files
from .refs import Reference, RefKind, extract

__version__ = "0.1.0"
__all__ = [
    "check_file",
    "find_context_files",
    "extract",
    "Report",
    "Finding",
    "Reference",
    "RefKind",
]
