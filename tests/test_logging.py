"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging

import pytest
import structlog

from app.logging import setup_logging


class TestSetupLogging:
    """Verify structlog configuration."""

    def teardown_method(self) -> None:
        """Reset structlog and stdlib logging after each test."""
        structlog.reset_defaults()
        root = logging.getLogger()
        root.handlers.clear()

    def test_setup_logging_configures_structlog(self) -> None:
        setup_logging(log_level="INFO", debug=False)
        logger = structlog.get_logger("test")
        assert logger is not None

    def test_json_renderer_in_production_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(log_level="INFO", debug=False)
        logger = structlog.get_logger("test")
        logger.info("test_event", key="value")

        captured = capsys.readouterr()
        line = captured.out.strip()
        parsed = json.loads(line)
        assert parsed["event"] == "test_event"
        assert parsed["key"] == "value"
        assert parsed["log_level"] == "info"

    def test_console_renderer_in_debug_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(log_level="DEBUG", debug=True)
        logger = structlog.get_logger("test")
        logger.info("test_event", key="value")

        captured = capsys.readouterr()
        assert "test_event" in captured.out
        assert "key" in captured.out

    def test_contextvars_merged_into_log(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(log_level="INFO", debug=False)
        structlog.contextvars.bind_contextvars(request_id="req-abc-123")
        try:
            logger = structlog.get_logger("test")
            logger.info("with_context")
            captured = capsys.readouterr()
            parsed = json.loads(captured.out.strip())
            assert parsed["request_id"] == "req-abc-123"
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

    def test_iso_timestamp_present(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(log_level="INFO", debug=False)
        logger = structlog.get_logger("test")
        logger.info("ts_check")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert "timestamp" in parsed

    def test_log_level_in_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(log_level="DEBUG", debug=False)
        logger = structlog.get_logger("test")
        logger.warning("warn_msg")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["log_level"] == "warning"
