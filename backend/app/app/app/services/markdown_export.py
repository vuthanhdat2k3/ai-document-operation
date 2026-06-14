"""Markdown export service for rendering reports to formatted Markdown."""

from __future__ import annotations

import logging
from datetime import datetime

from app.db.models.report import Report

logger = logging.getLogger(__name__)


class MarkdownExporter:
    """Renders a ``Report`` into a well-structured Markdown document.

    The output follows a consistent section hierarchy:
    ``# Title → ## Overview → ## Key Findings → ## Extracted Fields →
    ## Risks → ## Compliance Checklist → ## Recommendations``

    Not all sections are present in every report type; the exporter
    gracefully omits empty or irrelevant sections.
    """

    def export(self, report: Report) -> str:
        """Export a report to Markdown format.

        Args:
            report: The ``Report`` ORM instance with populated ``content``.

        Returns:
            A formatted Markdown string.
        """
        content = report.content
        sections: list[str] = []

        sections.append(self._render_title(report))
        sections.append(self._render_metadata(report))
        sections.append(self._render_overview(content.get("overview", {})))

        if content.get("report_type") == "risk_assessment" and content.get("risk_summary"):
            sections.append(self._render_risk_summary(content["risk_summary"]))

        sections.append(self._render_key_findings(content.get("key_findings", [])))
        sections.append(self._render_extracted_fields(content.get("extracted_fields", [])))
        sections.append(self._render_risks(content.get("risks", [])))
        sections.append(self._render_checklist(content.get("checklist", [])))
        sections.append(self._render_recommendations(content.get("recommendations", [])))
        sections.append(self._render_footer(report))

        return "\n".join(s for s in sections if s)

    def _render_title(self, report: Report) -> str:
        return f"# {report.title}\n"

    def _render_metadata(self, report: Report) -> str:
        lines = [
            "| Property | Value |",
            "|---|---|",
            f"| **Report ID** | `{report.id}` |",
            f"| **Report Type** | {report.report_type} |",
            f"| **Generated At** | {self._format_dt(report.generated_at)} |",
        ]
        if report.document_id:
            lines.append(f"| **Document ID** | `{report.document_id}` |")
        return "\n".join(lines) + "\n"

    def _render_overview(self, overview: dict) -> str:
        if not overview:
            return ""

        lines = ["## Overview\n"]
        lines.append("| Property | Value |")
        lines.append("|---|---|")

        label_map = {
            "filename": "Filename",
            "mime_type": "MIME Type",
            "file_size_bytes": "File Size",
            "page_count": "Page Count",
            "document_type": "Document Type",
            "status": "Status",
            "uploaded_at": "Uploaded At",
            "processed_at": "Processed At",
        }

        for key, label in label_map.items():
            value = overview.get(key)
            if value is None:
                continue
            if key == "file_size_bytes" and isinstance(value, int):
                value = self._format_file_size(value)
            elif key in ("uploaded_at", "processed_at") and isinstance(value, str):
                try:
                    value = self._format_dt(datetime.fromisoformat(value))
                except (ValueError, TypeError):
                    pass
            lines.append(f"| **{label}** | {value} |")

        return "\n".join(lines) + "\n"

    def _render_risk_summary(self, summary: dict) -> str:
        lines = ["## Risk Summary\n"]
        lines.append("| Severity | Count |")
        lines.append("|---|---|")
        for sev in ("critical", "high", "medium", "low", "info"):
            count = summary.get(sev, 0)
            if count > 0:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(sev, "")
                lines.append(f"| {sev.capitalize()} | {count} |")
        lines.append("")
        lines.append(f"**Total risks:** {summary.get('total', 0)} | "
                      f"**Open:** {summary.get('open', 0)} | "
                      f"**Resolved:** {summary.get('resolved', 0)}")
        return "\n".join(lines) + "\n"

    def _render_key_findings(self, findings: list[str]) -> str:
        if not findings:
            return ""
        lines = ["## Key Findings\n"]
        for finding in findings:
            lines.append(f"- {finding}")
        return "\n".join(lines) + "\n"

    def _render_extracted_fields(self, fields: list[dict]) -> str:
        if not fields:
            return ""

        lines = ["## Extracted Fields\n"]

        has_raw_text = any(f.get("raw_text") for f in fields)

        if has_raw_text:
            lines.append("| Field | Value | Confidence | Page | Verified |")
            lines.append("|---|---|---|---|---|")
            for f in fields:
                name = f.get("field_name", "")
                value = self._format_field_value(f.get("field_value"))
                conf = self._format_confidence(f.get("confidence"))
                page = f.get("page_number", "-") or "-"
                verified = "✅" if f.get("is_verified") else "❌"
                lines.append(f"| {name} | {value} | {conf} | {page} | {verified} |")
        else:
            lines.append("| Field | Value | Confidence |")
            lines.append("|---|---|---|")
            for f in fields:
                name = f.get("field_name", "")
                value = self._format_field_value(f.get("field_value"))
                conf = self._format_confidence(f.get("confidence"))
                lines.append(f"| {name} | {value} | {conf} |")

        return "\n".join(lines) + "\n"

    def _render_risks(self, risks: list[dict]) -> str:
        if not risks:
            return ""

        lines = ["## Risks\n"]
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.get("severity", ""), 5))

        for r in sorted_risks:
            severity = r.get("severity", "unknown").upper()
            title = r.get("title", "Untitled")
            category = r.get("category", "")
            status = r.get("status", "")
            lines.append(f"### [{severity}] {title}\n")
            meta_parts = []
            if category:
                meta_parts.append(f"**Category:** {category}")
            if status:
                meta_parts.append(f"**Status:** {status}")
            page = r.get("page_number")
            if page:
                meta_parts.append(f"**Page:** {page}")
            if meta_parts:
                lines.append(" | ".join(meta_parts) + "\n")

            description = r.get("description")
            if description:
                lines.append(f"{description}\n")

            evidence = r.get("evidence")
            if evidence and isinstance(evidence, dict):
                lines.append("**Evidence:**\n")
                for ek, ev in evidence.items():
                    lines.append(f"- {ek}: {ev}")
                lines.append("")

            resolution = r.get("resolution")
            if resolution:
                lines.append(f"**Resolution:** {resolution}\n")

        return "\n".join(lines) + "\n"

    def _render_checklist(self, checklist: list[dict]) -> str:
        if not checklist:
            return ""

        lines = ["## Compliance Checklist\n"]
        status_icons = {"pass": "✅", "fail": "❌", "warning": "⚠️", "pending": "⏳"}
        for item in checklist:
            icon = status_icons.get(item.get("status", ""), "❓")
            lines.append(f"- {icon} {item.get('item', '')}")
        return "\n".join(lines) + "\n"

    def _render_recommendations(self, recommendations: list[str]) -> str:
        if not recommendations:
            return ""
        lines = ["## Recommendations\n"]
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        return "\n".join(lines) + "\n"

    def _render_footer(self, report: Report) -> str:
        return (
            "---\n"
            f"*Report generated on {self._format_dt(report.generated_at)} "
            f"by AI Document Operations Agent*\n"
        )

    @staticmethod
    def _format_field_value(value: dict | list | str | None) -> str:
        if value is None:
            return "-"
        if isinstance(value, dict):
            parts = [f"{k}: {v}" for k, v in value.items()]
            return "; ".join(parts) if parts else "-"
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    @staticmethod
    def _format_confidence(confidence: float | None) -> str:
        if confidence is None:
            return "N/A"
        pct = round(confidence * 100, 1)
        if pct >= 80:
            return f"{pct}% 🟢"
        if pct >= 50:
            return f"{pct}% 🟡"
        return f"{pct}% 🔴"

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def _format_dt(dt: datetime | None) -> str:
        if dt is None:
            return "N/A"
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
