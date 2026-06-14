"""PDF export service converting Markdown content to styled PDF."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_WEASYPRINT_AVAILABLE = False
try:
    import weasyprint  # type: ignore[import-untyped]

    _WEASYPRINT_AVAILABLE = True
except ImportError:
    logger.info(
        "weasyprint is not installed; PDF export will fall back to HTML. "
        "Install with: pip install weasyprint"
    )


class PdfExporter:
    """Converts Markdown content into a styled PDF document.

    The pipeline is: Markdown → HTML → PDF.

    If ``weasyprint`` is installed the HTML is rendered to PDF. Otherwise
    the raw HTML is returned as UTF-8 bytes so the caller can still serve
    a downloadable file.
    """

    def export(self, markdown_content: str) -> bytes:
        """Convert Markdown to PDF (or HTML fallback) bytes.

        Args:
            markdown_content: The Markdown string to convert.

        Returns:
            PDF bytes if weasyprint is available, otherwise HTML bytes.
        """
        html = self._markdown_to_html(markdown_content)
        full_html = self._wrap_with_template(html)

        if _WEASYPRINT_AVAILABLE:
            try:
                return self._render_pdf(full_html)
            except Exception:
                logger.exception("weasyprint rendering failed; falling back to HTML")
                return full_html.encode("utf-8")

        return full_html.encode("utf-8")

    def _markdown_to_html(self, md: str) -> str:
        """Convert Markdown to HTML using a simple built-in converter.

        Handles headers, bold, italic, tables, lists, horizontal rules,
        code blocks, and inline code. No external dependencies required.
        """
        lines = md.split("\n")
        html_lines: list[str] = []
        in_table = False
        in_list = False
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    html_lines.append("</code></pre>")
                    in_code_block = False
                else:
                    html_lines.append("<pre><code>")
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(self._escape_html(stripped))
                continue

            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if in_table:
                    html_lines.append("</tbody></table>")
                    in_table = False
                html_lines.append("")
                continue

            if stripped == "---":
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if in_table:
                    html_lines.append("</tbody></table>")
                    in_table = False
                html_lines.append("<hr>")
                continue

            header_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if header_match:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if in_table:
                    html_lines.append("</tbody></table>")
                    in_table = False
                level = len(header_match.group(1))
                text = self._inline_format(header_match.group(2))
                html_lines.append(f"<h{level}>{text}</h{level}>")
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]

                if all(re.match(r"^[-:]+$", c) for c in cells):
                    continue

                if not in_table:
                    in_table = True
                    html_lines.append(
                        "<table><thead><tr>"
                        + "".join(f"<th>{self._inline_format(c)}</th>" for c in cells)
                        + "</tr></thead><tbody>"
                    )
                else:
                    html_lines.append(
                        "<tr>"
                        + "".join(f"<td>{self._inline_format(c)}</td>" for c in cells)
                        + "</tr>"
                    )
                continue

            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False

            list_match = re.match(r"^[-*]\s+(.+)$", stripped)
            numbered_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if list_match:
                if not in_list:
                    in_list = True
                    html_lines.append("<ul>")
                html_lines.append(f"<li>{self._inline_format(list_match.group(1))}</li>")
                continue
            elif numbered_match:
                if not in_list:
                    in_list = True
                    html_lines.append("<ol>")
                html_lines.append(f"<li>{self._inline_format(numbered_match.group(2))}</li>")
                continue

            if in_list:
                html_lines.append("</ul>")
                in_list = False

            html_lines.append(f"<p>{self._inline_format(stripped)}</p>")

        if in_list:
            html_lines.append("</ul>")
        if in_table:
            html_lines.append("</tbody></table>")
        if in_code_block:
            html_lines.append("</code></pre>")

        return "\n".join(html_lines)

    def _inline_format(self, text: str) -> str:
        """Apply inline Markdown formatting: bold, italic, code, links."""
        text = self._escape_html(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        text = re.sub(
            r"\[(.+?)\]\((.+?)\)",
            r'<a href="\2">\1</a>',
            text,
        )
        return text

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _render_pdf(self, html: str) -> bytes:
        """Render HTML to PDF using weasyprint."""
        doc = weasyprint.HTML(string=html)
        return doc.write_pdf()

    def _wrap_with_template(self, body_html: str) -> str:
        """Wrap body HTML with a professional CSS template including headers/footers."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Document Report</title>
<style>
    @page {{
        size: A4;
        margin: 2.5cm 2cm 3cm 2cm;
        @top-center {{
            content: "AI Document Operations Agent — Report";
            font-size: 8pt;
            color: #888;
            border-bottom: 0.5pt solid #ccc;
            padding-bottom: 4pt;
        }}
        @bottom-center {{
            content: "Page " counter(page) " of " counter(pages);
            font-size: 8pt;
            color: #888;
            border-top: 0.5pt solid #ccc;
            padding-top: 4pt;
        }}
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.6;
        color: #1a1a1a;
        max-width: 100%;
    }}
    h1 {{
        font-size: 20pt;
        color: #0d1b2a;
        border-bottom: 2pt solid #1b4965;
        padding-bottom: 6pt;
        margin-top: 0;
    }}
    h2 {{
        font-size: 14pt;
        color: #1b4965;
        border-bottom: 1pt solid #bee9e8;
        padding-bottom: 4pt;
        margin-top: 18pt;
    }}
    h3 {{
        font-size: 12pt;
        color: #274c77;
        margin-top: 12pt;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 10pt 0;
        font-size: 9pt;
    }}
    thead {{
        background-color: #1b4965;
        color: #ffffff;
    }}
    th, td {{
        border: 1pt solid #d4d4d4;
        padding: 6pt 8pt;
        text-align: left;
        vertical-align: top;
    }}
    tbody tr:nth-child(even) {{
        background-color: #f8f9fa;
    }}
    ul, ol {{
        margin: 6pt 0;
        padding-left: 20pt;
    }}
    li {{
        margin-bottom: 4pt;
    }}
    code {{
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        background-color: #f1f3f5;
        padding: 1pt 4pt;
        border-radius: 3pt;
        font-size: 9pt;
    }}
    pre {{
        background-color: #f1f3f5;
        border: 1pt solid #d4d4d4;
        border-radius: 4pt;
        padding: 10pt;
        overflow-x: auto;
        font-size: 9pt;
    }}
    pre code {{
        background-color: transparent;
        padding: 0;
    }}
    hr {{
        border: none;
        border-top: 1pt solid #d4d4d4;
        margin: 16pt 0;
    }}
    a {{
        color: #1b4965;
        text-decoration: underline;
    }}
    p {{
        margin: 6pt 0;
    }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""
