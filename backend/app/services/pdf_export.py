"""Render a run report as a PDF via Jinja2 + WeasyPrint."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.ai.schemas import Report
from app.services.pdf_errors import PdfExportUnavailableError

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _configure_weasyprint_library_path() -> None:
    """Help WeasyPrint find Homebrew libs on macOS (pango/glib)."""
    if sys.platform != "darwin":
        return
    for lib_dir in (Path("/opt/homebrew/lib"), Path("/usr/local/lib")):
        if not lib_dir.is_dir():
            continue
        path = str(lib_dir)
        existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        if path not in existing.split(":"):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
                f"{path}:{existing}" if existing else path
            )
        break


def _collect_source_ids(report: Report) -> list[UUID]:
    """Walk report sections in UI order and return unique source ids."""
    seen: set[UUID] = set()
    ordered: list[UUID] = []

    def add(ids: list[UUID]) -> None:
        for sid in ids:
            if sid not in seen:
                seen.add(sid)
                ordered.append(sid)

    for metric in report.key_metrics:
        add(list(metric.citations))

    if report.competitive_strategic_synthesis:
        synth = report.competitive_strategic_synthesis
        for ins in synth.dynamics:
            add(list(ins.citations))
        for ins in synth.implications:
            add(list(ins.citations))

    for ins in report.key_findings:
        add(list(ins.citations))
    for section in (report.market_trends, report.consumer_behavior):
        if section is not None:
            for ins in section.insights:
                add(list(ins.citations))
    for ins in report.opportunities:
        add(list(ins.citations))
    for ins in report.risks:
        add(list(ins.citations))
    for theme in report.themes:
        for ins in theme.insights:
            add(list(ins.citations))
    for comp in report.competitors:
        for ins in comp.insights:
            add(list(ins.citations))

    return ordered


def build_source_index(report: Report) -> dict[str, int]:
    """Map source UUID string → 1-based citation index."""
    return {str(sid): idx + 1 for idx, sid in enumerate(_collect_source_ids(report))}


def _report_from_dict(data: dict[str, Any]) -> Report:
    return Report.model_validate(data)


def render_report_pdf(
    report_data: dict[str, Any],
    *,
    run_id: UUID | None = None,
    topics: list[str] | None = None,
) -> bytes:
    """Render report JSONB to PDF bytes."""
    report = _report_from_dict(report_data)
    source_index = build_source_index(report)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")
    css_path = _TEMPLATES_DIR / "report.css"
    css_text = css_path.read_text(encoding="utf-8")

    html = template.render(
        report=report,
        source_index=source_index,
        run_id=str(run_id) if run_id else None,
        input_topics=topics or report.topics,
        css=css_text,
    )
    try:
        _configure_weasyprint_library_path()
        from weasyprint import HTML
    except OSError as exc:
        raise PdfExportUnavailableError() from exc
    return HTML(string=html, base_url=str(_TEMPLATES_DIR)).write_pdf()
