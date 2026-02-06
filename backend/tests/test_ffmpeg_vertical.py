"""Tests for vertical framing/resolution helpers."""
from app.config import settings
from app.utils.ffmpeg import (
    _build_vertical_base_filter,
    _resolve_vertical_dimensions,
    _round_even,
)


def test_resolve_vertical_dimensions_limit_upscale_1080p():
    width, height = _resolve_vertical_dimensions(1920, 1080, "limit_upscale")
    assert (width, height) == (settings.vertical_width, settings.vertical_height)


def test_resolve_vertical_dimensions_limit_upscale_720p():
    width, height = _resolve_vertical_dimensions(1280, 720, "limit_upscale")
    expected_width = _round_even(settings.vertical_min_height)
    expected_height = _round_even(int(round(settings.vertical_min_height * 16 / 9)))
    assert (width, height) == (expected_width, expected_height)


def test_resolve_vertical_dimensions_match_source():
    width, height = _resolve_vertical_dimensions(1920, 1080, "match_source")
    expected_width = _round_even(int(round(1080 * 9 / 16)))
    assert (width, height) == (expected_width, 1080)


def test_build_vertical_base_filter_fill():
    filtergraph, label = _build_vertical_base_filter(1080, 1920, "fill")
    assert "scale=1080:1920" in filtergraph
    assert "crop=1080:1920" in filtergraph
    assert label == "vbase"


def test_build_vertical_base_filter_blur():
    filtergraph, label = _build_vertical_base_filter(1080, 1920, "blur")
    assert "gblur" in filtergraph
    assert "overlay" in filtergraph
    assert label == "vbase"
