"""Unit tests for PDF export."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.ai.schemas import Insight, Report, Theme
from app.services.pdf_errors import PdfExportUnavailableError
from app.services.pdf_export import build_source_index, render_report_pdf


@pytest.fixture
def sample_report() -> Report:
    sid1 = uuid4()
    sid2 = uuid4()
    return Report(
        headline="Cloud security spending is accelerating across enterprise buyers.",
        executive_summary=(
            "Multiple sources report increased investment in cloud security tooling. "
            "Competitors are expanding managed detection offerings."
        ),
        key_findings=[
            Insight(
                statement="Enterprise cloud security budgets grew year over year.",
                citations=[sid1],
                judge_verdict="verified",
                judge_rationale="Supported by cited source excerpt.",
            ),
        ],
        themes=[
            Theme(
                title="Market growth",
                summary="Demand signals from analyst and vendor sources.",
                insights=[
                    Insight(
                        statement="MDR adoption is rising among mid-market firms.",
                        citations=[sid1, sid2],
                        judge_verdict="unsupported",
                        judge_rationale="Source discusses enterprise only.",
                    ),
                ],
            ),
        ],
        topics=["cloud security"],
        source_count=2,
        generated_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
    )


def test_build_source_index_order(sample_report: Report) -> None:
    idx = build_source_index(sample_report)
    assert len(idx) == 2
    assert all(isinstance(k, str) for k in idx)
    assert all(v >= 1 for v in idx.values())


def test_render_report_pdf(sample_report: Report) -> None:
    try:
        pdf = render_report_pdf(sample_report.model_dump(mode="json"))
    except PdfExportUnavailableError:
        pytest.skip("WeasyPrint native libraries not available on this host")

    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1024
