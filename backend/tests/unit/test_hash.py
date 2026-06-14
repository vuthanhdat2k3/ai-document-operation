"""Unit tests for app.utils.hash.content_hash."""

from __future__ import annotations

import hashlib

from app.utils.hash import content_hash


class TestContentHash:
    """SHA-256 content hashing tests."""

    def test_empty_bytes(self) -> None:
        result = content_hash(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_known_value(self) -> None:
        data = b"hello world"
        result = content_hash(data)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected

    def test_returns_hex_string(self) -> None:
        result = content_hash(b"test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        data = b"deterministic test"
        assert content_hash(data) == content_hash(data)

    def test_different_data_different_hash(self) -> None:
        assert content_hash(b"data1") != content_hash(b"data2")

    def test_binary_data(self) -> None:
        data = bytes(range(256))
        result = content_hash(data)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected

    def test_large_data(self) -> None:
        data = b"x" * 1_000_000
        result = content_hash(data)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected

    def test_unicode_bytes(self) -> None:
        data = "Hello, 世界!".encode("utf-8")
        result = content_hash(data)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected
