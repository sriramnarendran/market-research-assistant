"""PDF export errors."""

from __future__ import annotations


class PdfExportUnavailableError(RuntimeError):
    """Raised when WeasyPrint native libraries are missing."""

    def __init__(self) -> None:
        super().__init__(
            "PDF export requires WeasyPrint system libraries. "
            "On macOS: brew install pango gdk-pixbuf libffi. "
            "On Debian/Ubuntu: apt install libpango-1.0-0 libpangocairo-1.0-0 "
            "libgdk-pixbuf-2.0-0 libcairo2 shared-mime-info fonts-dejavu-core. "
            "Docker/production images include these automatically."
        )
