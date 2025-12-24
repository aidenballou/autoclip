"""Tests for clip processor logic."""
import pytest
from app.pipeline.clip_processor import (
    Segment,
    create_segments_from_scenes,
    merge_short_segments,
    split_long_segments,
    post_process_segments,
    generate_clips_from_video,
)


class TestSegment:
    """Tests for Segment dataclass."""
    
    def test_duration(self):
        seg = Segment(start=10.0, end=25.0)
        assert seg.duration == 15.0
    
    def test_repr(self):
        seg = Segment(start=0.0, end=10.0)
        assert "0.00-10.00" in repr(seg)
        assert "dur=10.00s" in repr(seg)


class TestCreateSegmentsFromScenes:
    """Tests for scene to segment conversion."""
    
    def test_empty_scenes(self):
        """With no scene changes, return single segment for whole video."""
        segments = create_segments_from_scenes([], 120.0)
        assert len(segments) == 1
        assert segments[0].start == 0
        assert segments[0].end == 120.0
    
    def test_single_scene(self):
        """Single scene creates two segments."""
        segments = create_segments_from_scenes([30.0], 60.0)
        assert len(segments) == 2
        assert segments[0].start == 0
        assert segments[0].end == 30.0
        assert segments[1].start == 30.0
        assert segments[1].end == 60.0
    
    def test_multiple_scenes(self):
        """Multiple scenes create correct segments."""
        segments = create_segments_from_scenes([10.0, 20.0, 30.0], 40.0)
        assert len(segments) == 4
        assert segments[0].end == 10.0
        assert segments[1].start == 10.0
        assert segments[1].end == 20.0
        assert segments[3].end == 40.0
    
    def test_scene_at_start(self):
        """Scene at time 0 shouldn't create empty segment."""
        segments = create_segments_from_scenes([0.0, 30.0], 60.0)
        # All segments should have positive duration
        for seg in segments:
            assert seg.duration > 0
    
    def test_duplicate_scenes(self):
        """Duplicate timestamps should be handled."""
        segments = create_segments_from_scenes([10.0, 10.0, 20.0], 30.0)
        # Should not have duplicate boundaries
        starts = [s.start for s in segments]
        assert len(starts) == len(set(starts))


class TestMergeShortSegments:
    """Tests for short segment merging."""
    
    def test_no_short_segments(self):
        """Segments already above minimum stay unchanged."""
        segments = [
            Segment(0, 10),
            Segment(10, 20),
            Segment(20, 30)
        ]
        result = merge_short_segments(segments, min_duration=5.0)
        assert len(result) == 3
    
    def test_merge_single_short(self):
        """Single short segment gets merged."""
        segments = [
            Segment(0, 10),
            Segment(10, 12),  # 2 seconds - short
            Segment(12, 25)
        ]
        result = merge_short_segments(segments, min_duration=5.0)
        assert len(result) == 2
    
    def test_merge_at_start(self):
        """Short segment at start merges with next."""
        segments = [
            Segment(0, 2),  # Short
            Segment(2, 15)
        ]
        result = merge_short_segments(segments, min_duration=5.0)
        assert len(result) == 1
        assert result[0].start == 0
        assert result[0].end == 15
    
    def test_merge_at_end(self):
        """Short segment at end merges with previous."""
        segments = [
            Segment(0, 10),
            Segment(10, 12)  # Short
        ]
        result = merge_short_segments(segments, min_duration=5.0)
        assert len(result) == 1
        assert result[0].start == 0
        assert result[0].end == 12
    
    def test_consecutive_short_segments(self):
        """Multiple consecutive short segments merge correctly."""
        segments = [
            Segment(0, 2),   # 2s
            Segment(2, 4),   # 2s
            Segment(4, 6),   # 2s
            Segment(6, 20)   # 14s
        ]
        result = merge_short_segments(segments, min_duration=5.0)
        # All short segments should be merged
        assert all(s.duration >= 5.0 for s in result)
    
    def test_single_segment(self):
        """Single segment list returns as-is."""
        segments = [Segment(0, 3)]  # Short but only segment
        result = merge_short_segments(segments, min_duration=5.0)
        assert len(result) == 1
        assert result[0].duration == 3
    
    def test_empty_list(self):
        """Empty list returns empty."""
        result = merge_short_segments([], min_duration=5.0)
        assert len(result) == 0


class TestSplitLongSegments:
    """Tests for long segment splitting."""
    
    def test_no_long_segments(self):
        """Segments already below maximum stay unchanged."""
        segments = [
            Segment(0, 30),
            Segment(30, 55),
            Segment(55, 80)
        ]
        result = split_long_segments(segments, max_duration=60.0)
        assert len(result) == 3
    
    def test_split_single_long(self):
        """Single long segment gets split."""
        segments = [Segment(0, 120)]  # 2 minutes
        result = split_long_segments(segments, max_duration=60.0)
        assert len(result) == 2
        assert result[0].duration <= 60.0
        assert result[1].duration <= 60.0
    
    def test_split_preserves_boundaries(self):
        """Split should start and end at original boundaries."""
        segments = [Segment(10, 190)]  # 180 seconds
        result = split_long_segments(segments, max_duration=60.0)
        assert result[0].start == 10
        assert result[-1].end == 190
    
    def test_split_creates_equal_parts(self):
        """Splits should be roughly equal."""
        segments = [Segment(0, 120)]  # 120 seconds
        result = split_long_segments(segments, max_duration=60.0)
        assert len(result) == 2
        # Should be exactly 60s each
        assert abs(result[0].duration - 60.0) < 0.01
        assert abs(result[1].duration - 60.0) < 0.01
    
    def test_split_odd_duration(self):
        """Odd duration splits evenly."""
        segments = [Segment(0, 100)]  # 100 seconds
        result = split_long_segments(segments, max_duration=60.0)
        assert len(result) == 2
        # Should split into 50s each
        assert abs(result[0].duration - 50.0) < 0.01
        assert abs(result[1].duration - 50.0) < 0.01
    
    def test_multiple_long_segments(self):
        """Multiple long segments all get split."""
        segments = [
            Segment(0, 120),    # 120s -> 2 parts
            Segment(120, 180),  # 60s -> stays
            Segment(180, 360)   # 180s -> 3 parts
        ]
        result = split_long_segments(segments, max_duration=60.0)
        assert len(result) == 6  # 2 + 1 + 3
        assert all(s.duration <= 60.0 for s in result)


class TestPostProcessSegments:
    """Tests for full post-processing pipeline."""
    
    def test_handles_empty(self):
        """Empty list returns empty."""
        result = post_process_segments([])
        assert len(result) == 0
    
    def test_handles_single_normal(self):
        """Single normal segment unchanged."""
        segments = [Segment(0, 30)]
        result = post_process_segments(segments, min_duration=5.0, max_duration=60.0)
        assert len(result) == 1
        assert result[0].duration == 30
    
    def test_split_then_merge_stable(self):
        """Splitting then merging produces stable result."""
        segments = [
            Segment(0, 120),   # Long -> split to 2x60
            Segment(120, 123)  # Short -> merge
        ]
        result = post_process_segments(segments, min_duration=5.0, max_duration=60.0)
        # After splitting 120s into 2x60, and processing, we get a stable result
        # where all segments satisfy constraints
        assert len(result) >= 2
        # All should be >= min duration (except possibly last if single)
        for seg in result:
            assert seg.duration >= 5.0 or len(result) == 1
        # All should be <= max duration
        assert all(s.duration <= 60.0 for s in result)
    
    def test_all_constraints_satisfied(self):
        """Result satisfies both min and max constraints."""
        segments = [
            Segment(0, 2),
            Segment(2, 5),
            Segment(5, 200),
            Segment(200, 202),
            Segment(202, 250)
        ]
        result = post_process_segments(segments, min_duration=5.0, max_duration=60.0)
        
        # All should be >= 5 seconds (except possibly last)
        for seg in result[:-1]:
            assert seg.duration >= 5.0 or len(result) == 1
        
        # All should be <= 60 seconds
        for seg in result:
            assert seg.duration <= 60.0
    
    def test_preserves_coverage(self):
        """Total duration should remain the same."""
        segments = [
            Segment(0, 50),
            Segment(50, 150),
            Segment(150, 200)
        ]
        original_duration = sum(s.duration for s in segments)
        result = post_process_segments(segments, min_duration=5.0, max_duration=60.0)
        result_duration = sum(s.duration for s in result)
        
        assert abs(original_duration - result_duration) < 0.01


class TestGenerateClipsFromVideo:
    """Tests for the main clip generation function."""
    
    def test_no_scenes_generates_clips(self):
        """Video with no scene changes still generates clips."""
        result = generate_clips_from_video([], 300.0, min_duration=5.0, max_duration=60.0)
        assert len(result) > 0
        assert all(s.duration <= 60.0 for s in result)
    
    def test_respects_max_duration(self):
        """All clips respect max duration."""
        scenes = [10, 30, 45, 100, 150, 200]
        result = generate_clips_from_video(scenes, 250.0, min_duration=5.0, max_duration=60.0)
        
        for seg in result:
            assert seg.duration <= 60.0
    
    def test_reasonable_clip_count(self):
        """Generates reasonable number of clips for long video."""
        # Simulate a long video with scenes every ~15 seconds
        scenes = list(range(0, 3600, 15))  # 1 hour video
        result = generate_clips_from_video(scenes, 3600.0, min_duration=5.0, max_duration=60.0)
        
        # Should have clips but not thousands
        assert len(result) > 10
        assert len(result) < 500
    
    def test_short_video(self):
        """Short video produces appropriate clips."""
        scenes = [5, 15, 25]
        result = generate_clips_from_video(scenes, 35.0, min_duration=5.0, max_duration=60.0)
        
        # Should have few clips
        assert len(result) <= 10
        # Total coverage should match video
        total = sum(s.duration for s in result)
        assert abs(total - 35.0) < 0.01

