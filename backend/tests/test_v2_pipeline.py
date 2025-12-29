"""Tests for V2 highlight-aware pipeline."""
import numpy as np
import pytest
from pathlib import Path

from app.pipeline.v2.config import V2PipelineConfig
from app.pipeline.v2.features import (
    ExtractedFeatures,
    z_score,
    smooth,
)
from app.pipeline.v2.anchors import (
    Anchor,
    detect_anchors,
    find_local_maxima,
    get_excitement_integral,
)
from app.pipeline.v2.boundaries import (
    BoundaryCandidate,
    compute_boundary_scores,
    find_valleys,
    get_best_boundary_in_range,
)
from app.pipeline.v2.windows import (
    ClipWindow,
    select_windows,
    select_start_boundary,
    select_end_boundary,
    compute_quality_score,
)
from app.pipeline.v2.post_filters import (
    compute_iou,
    resolve_overlaps,
    filter_boring,
    filter_by_quality_target,
    deduplicate_clips,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_config():
    """Create sample config for testing."""
    return V2PipelineConfig(
        step_sec=0.5,
        min_clip_seconds=5.0,
        max_clip_seconds=60.0,
        pre_max=14.0,
        pre_min=2.0,
        post_max=28.0,
        post_min=2.0,
        fallback_pre=8.0,
        fallback_post=12.0,
        anchor_suppression_window_sec=4.0,
        target_clip_count_soft=10,
        overlap_iou_threshold=0.35,
    )


@pytest.fixture
def sample_features():
    """Create sample features for testing."""
    duration = 120.0  # 2 minutes
    step_sec = 0.5
    num_samples = int(duration / step_sec) + 1
    
    times = np.arange(num_samples) * step_sec
    
    # Create synthetic audio with peaks at 30s and 90s
    audio_rms = np.ones(num_samples) * 30
    audio_rms[int(30 / step_sec)] = 60  # Peak at 30s
    audio_rms[int(90 / step_sec)] = 55  # Peak at 90s
    
    # Smooth it
    audio_rms = smooth(audio_rms, window=3)
    audio_rms_z = z_score(audio_rms)
    
    # Create synthetic motion with peaks at 30s and 90s
    motion_score = np.ones(num_samples) * 10
    motion_score[int(30 / step_sec)] = 30
    motion_score[int(90 / step_sec)] = 28
    motion_score = smooth(motion_score, window=3)
    motion_score_z = z_score(motion_score)
    
    # Excitement
    excitement = np.maximum(0, audio_rms_z) * 0.6 + np.maximum(0, motion_score_z) * 0.4
    
    # Scene cuts at certain points
    scene_cuts = [10.0, 25.0, 35.0, 60.0, 85.0, 100.0]
    
    return ExtractedFeatures(
        times=times,
        audio_rms=audio_rms,
        audio_rms_z=audio_rms_z,
        motion_score=motion_score,
        motion_score_z=motion_score_z,
        excitement=excitement,
        scene_cuts=scene_cuts,
        fade_timestamps=[5.0, 55.0],
        freeze_timestamps=[],
        duration=duration,
        step_sec=step_sec,
        version="test",
    )


@pytest.fixture
def sample_boundaries(sample_features, sample_config):
    """Create sample boundaries."""
    return compute_boundary_scores(sample_features, sample_config)


@pytest.fixture
def sample_anchors(sample_features, sample_config):
    """Create sample anchors."""
    return detect_anchors(sample_features, sample_config)


# =============================================================================
# Feature Tests
# =============================================================================

class TestFeatures:
    """Tests for feature extraction utilities."""
    
    def test_z_score_normal(self):
        """Z-score normalizes correctly."""
        arr = np.array([1, 2, 3, 4, 5])
        result = z_score(arr)
        
        # Mean should be ~0
        assert abs(np.mean(result)) < 1e-10
        # Std should be ~1
        assert abs(np.std(result) - 1.0) < 1e-10
    
    def test_z_score_constant(self):
        """Z-score handles constant arrays."""
        arr = np.array([5, 5, 5, 5])
        result = z_score(arr)
        
        # Should be all zeros for constant input
        assert np.all(result == 0)
    
    def test_smooth_applies_moving_average(self):
        """Smooth applies moving average correctly."""
        arr = np.array([0, 0, 10, 0, 0])
        result = smooth(arr, window=3)
        
        # The peak should spread out
        assert result[2] < 10
        assert result[1] > 0 or result[3] > 0
    
    def test_smooth_short_array(self):
        """Smooth handles arrays shorter than window."""
        arr = np.array([1, 2])
        result = smooth(arr, window=5)
        
        # Should return input unchanged
        assert np.array_equal(result, arr)


# =============================================================================
# Anchor Tests
# =============================================================================

class TestAnchors:
    """Tests for anchor detection."""
    
    def test_find_local_maxima_finds_peaks(self):
        """Find local maxima correctly identifies peaks."""
        times = np.arange(10) * 1.0
        arr = np.array([0, 1, 2, 1, 0, 0, 3, 2, 1, 0])
        
        maxima = find_local_maxima(arr, times, min_distance_sec=1.0, step_sec=1.0, threshold=0.0)
        
        # Should find peak at index 2 (value=2) and index 6 (value=3)
        times_found = [m[0] for m in maxima]
        assert 2.0 in times_found
        assert 6.0 in times_found
    
    def test_find_local_maxima_respects_threshold(self):
        """Find local maxima respects threshold."""
        times = np.arange(10) * 1.0
        arr = np.array([0, 1, 2, 1, 0, 0, 3, 2, 1, 0])
        
        maxima = find_local_maxima(arr, times, min_distance_sec=1.0, step_sec=1.0, threshold=2.5)
        
        # Only the peak at 6 (value=3) should pass threshold
        times_found = [m[0] for m in maxima]
        assert 6.0 in times_found
        assert 2.0 not in times_found
    
    def test_detect_anchors_finds_excitement_peaks(self, sample_features, sample_config):
        """Detect anchors finds excitement peaks."""
        anchors = detect_anchors(sample_features, sample_config)
        
        # Should find anchors near our synthetic peaks at 30s and 90s
        anchor_times = [a.time_sec for a in anchors]
        
        # Allow some tolerance
        has_peak_near_30 = any(abs(t - 30) < 5 for t in anchor_times)
        has_peak_near_90 = any(abs(t - 90) < 5 for t in anchor_times)
        
        assert has_peak_near_30, f"Expected anchor near 30s, found: {anchor_times}"
        assert has_peak_near_90, f"Expected anchor near 90s, found: {anchor_times}"
    
    def test_get_excitement_integral(self, sample_features):
        """Excitement integral computes correctly."""
        # Integral over whole range
        full_integral = get_excitement_integral(sample_features, 0, sample_features.duration)
        assert full_integral > 0
        
        # Integral of partial range should be less
        partial_integral = get_excitement_integral(sample_features, 0, 60)
        assert partial_integral < full_integral


# =============================================================================
# Boundary Tests
# =============================================================================

class TestBoundaries:
    """Tests for boundary scoring."""
    
    def test_find_valleys_finds_minima(self):
        """Find valleys correctly identifies local minima."""
        times = np.arange(10) * 1.0
        arr = np.array([5, 3, 1, 3, 5, 5, 2, 4, 5, 5])  # Valleys at 2 and 6
        
        # Use z-scored for proper valley strength
        arr_z = z_score(arr)
        valleys = find_valleys(arr_z, times, step_sec=1.0, min_spacing_sec=1.0)
        
        valley_times = [v[0] for v in valleys]
        assert 2.0 in valley_times
        assert 6.0 in valley_times
    
    def test_compute_boundary_scores_near_scene_cuts(self, sample_features, sample_config):
        """Boundary scores are high near scene cuts."""
        boundaries = compute_boundary_scores(sample_features, sample_config)
        
        # Find boundary score near scene cut at 25s
        boundaries_near_25 = [b for b in boundaries if abs(b.time_sec - 25) < 1.0]
        
        assert len(boundaries_near_25) > 0
        assert any(b.scene_strength > 0.5 for b in boundaries_near_25)
    
    def test_get_best_boundary_in_range(self, sample_boundaries):
        """Get best boundary in range returns highest score."""
        best = get_best_boundary_in_range(sample_boundaries, 20, 40)
        
        if best:
            # Verify it's actually the best in range
            in_range = [b for b in sample_boundaries if 20 <= b.time_sec <= 40]
            max_score = max(b.score for b in in_range)
            assert best.score == max_score


# =============================================================================
# Window Selection Tests
# =============================================================================

class TestWindows:
    """Tests for window selection."""
    
    def test_select_start_boundary_snaps_to_best(self, sample_boundaries, sample_config):
        """Start boundary snaps to best boundary in search range."""
        anchor_time = 30.0
        
        start, score, reason = select_start_boundary(
            anchor_time, sample_boundaries, sample_config, 120.0
        )
        
        # Start should be before anchor
        assert start < anchor_time
        # Should be within configured range
        assert start >= anchor_time - sample_config.pre_max
    
    def test_select_start_boundary_fallback(self, sample_config):
        """Start boundary falls back when no boundaries available."""
        anchor_time = 30.0
        
        start, score, reason = select_start_boundary(
            anchor_time, [], sample_config, 120.0
        )
        
        assert reason == "fallback_offset"
        assert start == anchor_time - sample_config.fallback_pre
    
    def test_select_windows_respects_duration_limits(
        self, sample_anchors, sample_boundaries, sample_features, sample_config
    ):
        """Selected windows respect min/max duration."""
        windows = select_windows(
            sample_anchors, sample_boundaries, sample_features, sample_config
        )
        
        for window in windows:
            assert window.duration >= sample_config.min_clip_seconds, \
                f"Window duration {window.duration} < min {sample_config.min_clip_seconds}"
            assert window.duration <= sample_config.max_clip_seconds, \
                f"Window duration {window.duration} > max {sample_config.max_clip_seconds}"
    
    def test_compute_quality_score_components(self, sample_features, sample_config):
        """Quality score computation includes all components."""
        quality, excitement, dead_penalty, boundary_qual, narrative = compute_quality_score(
            start_sec=20.0,
            end_sec=40.0,
            anchor_time_sec=30.0,
            anchor_score=1.0,
            features=sample_features,
            start_boundary_score=0.5,
            end_boundary_score=0.5,
            config=sample_config,
        )
        
        # All components should be non-negative
        assert excitement >= 0
        assert dead_penalty >= 0
        assert boundary_qual >= 0
        assert narrative >= 0


# =============================================================================
# Post-Filter Tests
# =============================================================================

class TestPostFilters:
    """Tests for post-processing filters."""
    
    def test_compute_iou_no_overlap(self):
        """IoU is 0 for non-overlapping windows."""
        w1 = ClipWindow(
            start_sec=0, end_sec=10, anchor_time_sec=5, anchor_score=1.0,
            quality_score=1.0, excitement_score=1.0, dead_time_penalty=0,
            boundary_quality=1.0, narrative_score=1.0,
            start_boundary_score=1.0, end_boundary_score=1.0,
            start_reason="test", end_reason="test"
        )
        w2 = ClipWindow(
            start_sec=20, end_sec=30, anchor_time_sec=25, anchor_score=1.0,
            quality_score=1.0, excitement_score=1.0, dead_time_penalty=0,
            boundary_quality=1.0, narrative_score=1.0,
            start_boundary_score=1.0, end_boundary_score=1.0,
            start_reason="test", end_reason="test"
        )
        
        iou = compute_iou(w1, w2)
        assert iou == 0.0
    
    def test_compute_iou_full_overlap(self):
        """IoU is 1 for identical windows."""
        w1 = ClipWindow(
            start_sec=0, end_sec=10, anchor_time_sec=5, anchor_score=1.0,
            quality_score=1.0, excitement_score=1.0, dead_time_penalty=0,
            boundary_quality=1.0, narrative_score=1.0,
            start_boundary_score=1.0, end_boundary_score=1.0,
            start_reason="test", end_reason="test"
        )
        
        iou = compute_iou(w1, w1)
        assert iou == 1.0
    
    def test_compute_iou_partial_overlap(self):
        """IoU computed correctly for partial overlap."""
        w1 = ClipWindow(
            start_sec=0, end_sec=10, anchor_time_sec=5, anchor_score=1.0,
            quality_score=1.0, excitement_score=1.0, dead_time_penalty=0,
            boundary_quality=1.0, narrative_score=1.0,
            start_boundary_score=1.0, end_boundary_score=1.0,
            start_reason="test", end_reason="test"
        )
        w2 = ClipWindow(
            start_sec=5, end_sec=15, anchor_time_sec=10, anchor_score=1.0,
            quality_score=1.0, excitement_score=1.0, dead_time_penalty=0,
            boundary_quality=1.0, narrative_score=1.0,
            start_boundary_score=1.0, end_boundary_score=1.0,
            start_reason="test", end_reason="test"
        )
        
        # Intersection: 5-10 = 5
        # Union: 0-15 = 15
        # IoU = 5/15 = 0.333...
        iou = compute_iou(w1, w2)
        assert abs(iou - 5/15) < 0.01
    
    def test_resolve_overlaps_removes_duplicates(self, sample_config):
        """Overlap resolution removes highly overlapping clips."""
        windows = [
            ClipWindow(
                start_sec=0, end_sec=20, anchor_time_sec=10, anchor_score=1.0,
                quality_score=0.8, excitement_score=1.0, dead_time_penalty=0,
                boundary_quality=1.0, narrative_score=1.0,
                start_boundary_score=1.0, end_boundary_score=1.0,
                start_reason="test", end_reason="test"
            ),
            ClipWindow(
                start_sec=5, end_sec=25, anchor_time_sec=15, anchor_score=1.0,
                quality_score=0.9, excitement_score=1.0, dead_time_penalty=0,
                boundary_quality=1.0, narrative_score=1.0,
                start_boundary_score=1.0, end_boundary_score=1.0,
                start_reason="test", end_reason="test"
            ),
        ]
        
        kept, decisions = resolve_overlaps(windows, sample_config)
        
        # One should be dropped due to high IoU
        assert len(kept) == 1
        # Higher quality should be kept
        assert kept[0].quality_score == 0.9
    
    def test_filter_by_quality_target(self, sample_config):
        """Quality filter reduces to target count."""
        # Create more windows than target
        windows = []
        for i in range(20):
            windows.append(ClipWindow(
                start_sec=i*10, end_sec=i*10+8, anchor_time_sec=i*10+4, anchor_score=1.0,
                quality_score=i/20, excitement_score=1.0, dead_time_penalty=0,
                boundary_quality=1.0, narrative_score=1.0,
                start_boundary_score=1.0, end_boundary_score=1.0,
                start_reason="test", end_reason="test"
            ))
        
        # Config has target of 10
        kept, decisions = filter_by_quality_target(windows, sample_config)
        
        assert len(kept) == sample_config.target_clip_count_soft


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the full pipeline."""
    
    def test_full_pipeline_produces_clips(self, sample_features, sample_config):
        """Full pipeline produces valid clips."""
        anchors = detect_anchors(sample_features, sample_config)
        boundaries = compute_boundary_scores(sample_features, sample_config)
        windows = select_windows(anchors, boundaries, sample_features, sample_config)
        
        # Should produce some clips
        assert len(windows) > 0
        
        # All clips should have valid quality scores
        for window in windows:
            assert window.quality_score > 0
    
    def test_deterministic_output_with_seed(self, sample_features, sample_config):
        """Pipeline produces deterministic output."""
        # Run twice
        anchors1 = detect_anchors(sample_features, sample_config)
        boundaries1 = compute_boundary_scores(sample_features, sample_config)
        windows1 = select_windows(anchors1, boundaries1, sample_features, sample_config)
        
        anchors2 = detect_anchors(sample_features, sample_config)
        boundaries2 = compute_boundary_scores(sample_features, sample_config)
        windows2 = select_windows(anchors2, boundaries2, sample_features, sample_config)
        
        # Should be identical
        assert len(windows1) == len(windows2)
        
        for w1, w2 in zip(windows1, windows2):
            assert w1.start_sec == w2.start_sec
            assert w1.end_sec == w2.end_sec
            assert w1.quality_score == w2.quality_score

