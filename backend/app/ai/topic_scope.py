"""Keep synthesized reports focused on user-supplied research keywords."""

from __future__ import annotations

from app.ai.schemas import Insight, KeyMetric, Report
from app.ai.topic_match import is_user_topic_name, topic_matches_text


def scope_report_to_topics(report: Report, topics: list[str]) -> Report:
    """Drop competitor rows and de-prioritize findings that aren't about user topics."""
    if not topics:
        return report

    competitors = [
        c
        for c in report.competitors
        if is_user_topic_name(c.competitor, topics)
    ]
    key_findings = _prioritize_topic_findings(report.key_findings, topics)
    key_metrics = _prioritize_topic_metrics(report.key_metrics, topics)

    headline = report.headline
    if headline and not _text_about_user_topics(headline, topics):
        for finding in key_findings:
            if _text_about_user_topics(finding.statement, topics):
                headline = finding.statement[:240]
                break

    return report.model_copy(
        update={
            "headline": headline,
            "competitors": competitors,
            "key_findings": key_findings,
            "key_metrics": key_metrics,
        }
    )


def _text_about_user_topics(text: str, topics: list[str]) -> bool:
    return any(topic_matches_text(topic, text) for topic in topics)


def _prioritize_topic_findings(findings: list[Insight], topics: list[str]) -> list[Insight]:
    primary = [f for f in findings if _text_about_user_topics(f.statement, topics)]
    secondary = [f for f in findings if f not in primary]
    return primary + secondary


def _prioritize_topic_metrics(metrics: list[KeyMetric], topics: list[str]) -> list[KeyMetric]:
    primary = [
        m
        for m in metrics
        if _text_about_user_topics(f"{m.label} {m.value} {m.context}", topics)
    ]
    secondary = [m for m in metrics if m not in primary]
    return primary + secondary
