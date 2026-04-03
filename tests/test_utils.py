"""Tests for utility functions."""

from podcraft.utils import slugify, format_duration


def test_slugify_english():
    assert slugify("EP01: My First Episode") == "ep01-my-first-episode"


def test_slugify_chinese():
    assert slugify("EP01: 视觉审美基础") == "ep01-视觉审美基础"


def test_slugify_special_chars():
    assert slugify("Hello, World! @#$") == "hello-world"


def test_slugify_max_length():
    long_text = "a" * 100
    assert len(slugify(long_text)) <= 60


def test_format_duration():
    assert format_duration(0) == "00:00:00"
    assert format_duration(65) == "00:01:05"
    assert format_duration(3661) == "01:01:01"


def test_format_duration_fractional():
    assert format_duration(90.7) == "00:01:30"
