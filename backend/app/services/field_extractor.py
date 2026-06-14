"""Field extractor using LLM with rule-based fallback."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFieldValue:
    """Represents a single extracted field from a document."""

    field_name: str
    field_value: dict[str, Any]
    raw_text: str = ""
    confidence: float = 0.0
    page_number: int | None = None


EXTRACTION_PROMPT_TEMPLATE = """You are a document field extraction assistant. Extract the following fields from the document text.

DOCUMENT TYPE: {document_type}

FIELDS TO EXTRACT (JSON Schema):
{schema_json}

DOCUMENT TEXT:
\"\"\"
{text}
\"\"\"

Extract each field and return a JSON array of objects. Each object must have:
- "field_name": the field name from the schema
- "field_value": the extracted value (matching the schema type)
- "raw_text": the exact text snippet from which the value was extracted
- "confidence": a float between 0.0 and 1.0 indicating extraction confidence

If a field cannot be found, set "field_value" to null, "confidence" to 0.0, and "raw_text" to "".

Return ONLY a valid JSON array, no other text. Example:
[
  {{"field_name": "contract_number", "field_value": {{"value": "HD-2024-001"}}, "raw_text": "Số: HD-2024-001", "confidence": 0.95}},
  {{"field_name": "total_amount", "field_value": {{"value": 50000000, "currency": "VND"}}, "raw_text": "Tổng cộng: 50,000,000 VND", "confidence": 0.9}}
]
"""


class FieldExtractor:
    """Extracts structured fields from document text.

    Uses LLM when available, falls back to rule-based extraction.
    """

    def __init__(self, llm_client: Any | None = None, model: str = "gpt-4o") -> None:
        self._llm = llm_client
        self._model = model

    async def extract(
        self, text: str, schema: dict[str, Any], document_type: str
    ) -> list[ExtractedFieldValue]:
        """Extract fields from text according to a schema definition.

        Args:
            text: The document text to extract from.
            schema: The extraction schema defining fields to extract.
            document_type: The classified document type.
        Returns:
            List of ExtractedFieldValue instances.
        """
        if not text or not text.strip():
            return []

        fields_def = schema.get("fields", schema.get("properties", {}))
        if not fields_def:
            logger.warning("Schema has no fields/properties defined")
            return []

        if self._llm is not None:
            try:
                return await self._extract_with_llm(text, schema, document_type)
            except Exception:
                logger.exception("LLM extraction failed, falling back to rules")

        return self._extract_with_rules(text, fields_def, document_type)

    async def _extract_with_llm(
        self, text: str, schema: dict[str, Any], document_type: str
    ) -> list[ExtractedFieldValue]:
        """Extract fields using an LLM."""
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

        prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            document_type=document_type,
            schema_json=schema_json,
            text=text[:8000],
        )

        response = await self._call_llm(prompt)
        return self._parse_llm_response(response)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM API. Override for different providers."""
        if self._llm is None:
            raise RuntimeError("No LLM client configured")

        if hasattr(self._llm, "chat"):
            messages = [{"role": "user", "content": prompt}]
            response = await self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or "[]"
        elif hasattr(self._llm, "generate"):
            result = await self._llm.generate(prompt)
            return result
        else:
            raise RuntimeError(f"Unsupported LLM client type: {type(self._llm)}")

    def _parse_llm_response(self, response: str) -> list[ExtractedFieldValue]:
        """Parse structured JSON from LLM response."""
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*", "", response)
            response = re.sub(r"\s*```$", "", response)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse LLM response as JSON")
                    return []
            else:
                logger.warning("No JSON array found in LLM response")
                return []

        if not isinstance(data, list):
            if isinstance(data, dict) and "fields" in data:
                data = data["fields"]
            else:
                logger.warning("LLM response is not a JSON array")
                return []

        results: list[ExtractedFieldValue] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            field_name = item.get("field_name", "")
            if not field_name:
                continue

            field_value = item.get("field_value")
            if field_value is None:
                field_value = {"value": None}
            elif not isinstance(field_value, dict):
                field_value = {"value": field_value}

            results.append(
                ExtractedFieldValue(
                    field_name=field_name,
                    field_value=field_value,
                    raw_text=item.get("raw_text", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    page_number=item.get("page_number"),
                )
            )

        return results

    def _extract_with_rules(
        self,
        text: str,
        fields_def: dict[str, Any],
        document_type: str,
    ) -> list[ExtractedFieldValue]:
        """Rule-based field extraction fallback."""
        results: list[ExtractedFieldValue] = []
        normalized = text.lower()

        for field_name, field_def in fields_def.items():
            field_type = field_def.get("type", "string") if isinstance(field_def, dict) else "string"
            patterns = self._get_extraction_patterns(field_name, field_type, document_type)

            best_match = ""
            best_confidence = 0.0

            for pattern, confidence in patterns:
                match = re.search(pattern, normalized, re.IGNORECASE | re.DOTALL)
                if match:
                    captured = match.group(1).strip() if match.lastindex else match.group(0).strip()
                    if captured and confidence > best_confidence:
                        best_match = captured
                        best_confidence = confidence

            if best_match:
                field_value = self._cast_value(best_match, field_type)
                results.append(
                    ExtractedFieldValue(
                        field_name=field_name,
                        field_value={"value": field_value},
                        raw_text=best_match,
                        confidence=best_confidence,
                    )
                )
            else:
                results.append(
                    ExtractedFieldValue(
                        field_name=field_name,
                        field_value={"value": None},
                        raw_text="",
                        confidence=0.0,
                    )
                )

        return results

    def _get_extraction_patterns(
        self, field_name: str, field_type: str, document_type: str
    ) -> list[tuple[str, float]]:
        """Get regex patterns for a field name."""
        name_lower = field_name.lower().replace("_", " ")
        patterns: list[tuple[str, float]] = []

        label_patterns = [
            rf"{re.escape(name_lower)}\s*[:：]\s*(.+?)(?:\n|$)",
            rf"{re.escape(name_lower)}\s*(?:là|is|la)\s*(.+?)(?:\n|$)",
        ]
        for p in label_patterns:
            patterns.append((p, 0.7))

        vn_mappings: dict[str, list[str]] = {
            "contract number": ["số hợp đồng", "số hđ", "hợp đồng số", "mã hợp đồng"],
            "invoice number": ["số hóa đơn", "mã hóa đơn", "hóa đơn số"],
            "date": ["ngày", "ngày ký", "ngày lập", "date"],
            "total amount": ["tổng cộng", "tổng tiền", "tổng thanh toán", "thành tiền"],
            "party a": ["bên a", "bên bán", "công ty", "甲方"],
            "party b": ["bên b", "bên mua", "khách hàng", "乙方"],
            "tax code": ["mã số thuế", "mst"],
            "address": ["địa chỉ", "address"],
            "phone": ["điện thoại", "sđt", "số điện thoại", "phone", "tel"],
            "email": ["email", "thư điện tử"],
        }

        for eng_key, vn_labels in vn_mappings.items():
            if eng_key in name_lower:
                for label in vn_labels:
                    patterns.append(
                        (rf"{re.escape(label)}\s*[:：]\s*(.+?)(?:\n|$)", 0.8)
                    )

        if field_type in ("number", "integer", "float"):
            patterns.append(
                (rf"{re.escape(name_lower)}\s*[:：]\s*([\d.,]+)", 0.6)
            )
        elif field_type == "date":
            patterns.append(
                (rf"{re.escape(name_lower)}\s*[:：]\s*(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}})", 0.6)
            )

        return patterns

    def _cast_value(self, raw: str, field_type: str) -> Any:
        """Cast extracted string value to the expected type."""
        cleaned = raw.strip().rstrip(";,. ")

        if field_type in ("number", "integer", "float"):
            cleaned_num = cleaned.replace(",", "").replace(" ", "")
            cleaned_num = re.sub(r"[^\d.\-]", "", cleaned_num)
            try:
                if field_type == "integer":
                    return int(float(cleaned_num))
                return float(cleaned_num)
            except ValueError:
                return cleaned

        if field_type == "boolean":
            return cleaned.lower() in ("true", "yes", "có", "đúng", "1")

        return cleaned
