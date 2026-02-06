"""Tests for niche and account functionality."""
import pytest
import json
from unittest.mock import AsyncMock, patch

from app.models.niche import Niche
from app.models.account import Account, Platform, AuthStatus
from app.services.niche_service import NicheService


class TestNicheModel:
    """Tests for Niche model."""
    
    def test_niche_to_dict(self):
        """Test niche serialization."""
        niche = Niche(
            id=1,
            name="Test Niche",
            description="A test niche",
            default_hashtags=json.dumps(["tag1", "tag2"]),
            default_caption_template="Test caption",
            default_text_overlay="Test overlay",
            default_text_position="bottom",
            default_text_color="#FFFFFF",
            default_text_size=48,
            default_audio_volume=30,
        )
        
        result = niche.to_dict()
        
        assert result["name"] == "Test Niche"
        assert result["description"] == "A test niche"
        assert result["default_hashtags"] == ["tag1", "tag2"]
        assert result["default_text_position"] == "bottom"
        assert result["default_text_size"] == 48
    
    def test_niche_repr(self):
        """Test niche string representation."""
        niche = Niche(id=1, name="Sports")
        assert "Sports" in repr(niche)
        assert "1" in repr(niche)


class TestAccountModel:
    """Tests for Account model."""
    
    def test_account_to_dict(self):
        """Test account serialization excludes sensitive data."""
        account = Account(
            id=1,
            niche_id=1,
            platform=Platform.YOUTUBE_SHORTS,
            handle="@testuser",
            display_name="Test User",
            auth_status=AuthStatus.CONNECTED,
            access_token="secret_token",
            refresh_token="secret_refresh",
            auto_upload=True,
        )
        
        result = account.to_dict()
        
        assert result["handle"] == "@testuser"
        assert result["platform"] == "youtube_shorts"
        assert result["auth_status"] == "connected"
        assert result["auto_upload"] is True
        # Sensitive data should not be in dict
        assert "access_token" not in result
        assert "refresh_token" not in result
    
    def test_platform_enum_values(self):
        """Test all platform enum values exist."""
        assert Platform.YOUTUBE_SHORTS.value == "youtube_shorts"
        assert Platform.TIKTOK.value == "tiktok"
        assert Platform.INSTAGRAM_REELS.value == "instagram_reels"
        assert Platform.TWITTER.value == "twitter"
        assert Platform.SNAPCHAT.value == "snapchat"
    
    def test_auth_status_enum_values(self):
        """Test all auth status enum values exist."""
        assert AuthStatus.NOT_CONNECTED.value == "not_connected"
        assert AuthStatus.CONNECTED.value == "connected"
        assert AuthStatus.EXPIRED.value == "expired"
        assert AuthStatus.ERROR.value == "error"
    
    def test_account_repr(self):
        """Test account string representation."""
        account = Account(
            id=1,
            niche_id=1,
            platform=Platform.TIKTOK,
            handle="@tiktoker"
        )
        assert "tiktok" in repr(account).lower()
        assert "@tiktoker" in repr(account)


class TestNicheServiceValidation:
    """Tests for NicheService validation logic."""
    
    def test_platform_validation(self):
        """Test that invalid platforms are rejected."""
        # This tests the validation logic - actual DB tests would need a test DB
        valid_platforms = [p.value for p in Platform]
        
        assert "youtube_shorts" in valid_platforms
        assert "invalid_platform" not in valid_platforms
    
    def test_hashtag_parsing(self):
        """Test hashtag JSON parsing."""
        hashtags_json = json.dumps(["nba", "basketball", "highlights"])
        parsed = json.loads(hashtags_json)
        
        assert len(parsed) == 3
        assert "nba" in parsed
    
    def test_empty_hashtags(self):
        """Test empty hashtags handling."""
        niche = Niche(
            id=1,
            name="Test",
            default_hashtags=None
        )
        
        result = niche.to_dict()
        assert result["default_hashtags"] == []


class TestPublishServiceValidation:
    """Tests for publish service validation logic."""
    
    def test_platform_specs_structure(self):
        """Test platform specs contain expected fields."""
        from app.services.publish_service import PLATFORM_SPECS, Platform
        
        for platform in Platform:
            if platform in PLATFORM_SPECS:
                specs = PLATFORM_SPECS[platform]
                # All specs should have these keys
                assert "max_duration" in specs
                assert "min_duration" in specs
                assert "aspect_ratio" in specs
    
    def test_youtube_shorts_specs(self):
        """Test YouTube Shorts specific requirements."""
        from app.services.publish_service import PLATFORM_SPECS, Platform
        
        specs = PLATFORM_SPECS[Platform.YOUTUBE_SHORTS]
        
        assert specs["max_duration"] == 60
        assert specs["aspect_ratio"] == "9:16"
        assert specs["recommended_resolution"] == (1080, 1920)
    
    def test_tiktok_specs(self):
        """Test TikTok specific requirements."""
        from app.services.publish_service import PLATFORM_SPECS, Platform
        
        specs = PLATFORM_SPECS[Platform.TIKTOK]
        
        assert specs["max_duration"] == 180
        assert specs["min_duration"] == 3
    
    def test_instagram_reels_specs(self):
        """Test Instagram Reels specific requirements."""
        from app.services.publish_service import PLATFORM_SPECS, Platform
        
        specs = PLATFORM_SPECS[Platform.INSTAGRAM_REELS]
        
        assert specs["max_duration"] == 90
        assert specs["aspect_ratio"] == "9:16"


class TestFFmpegOverlayFilters:
    """Tests for FFmpeg filter generation."""
    
    def test_text_filter_position_top(self):
        """Test text overlay positioned at top."""
        from app.utils.ffmpeg import _build_text_filter, TextOverlay
        
        overlay = TextOverlay(
            text="Test Text",
            position="top",
            font_size=48,
            font_color="#FFFFFF"
        )
        
        filter_str = _build_text_filter(overlay, 30.0)
        
        assert "drawtext" in filter_str
        assert "Test Text" in filter_str
        assert "h*0.1" in filter_str  # Top position
    
    def test_text_filter_position_bottom(self):
        """Test text overlay positioned at bottom."""
        from app.utils.ffmpeg import _build_text_filter, TextOverlay
        
        overlay = TextOverlay(
            text="Bottom Text",
            position="bottom",
            font_size=48,
            font_color="#FF0000"
        )
        
        filter_str = _build_text_filter(overlay, 30.0)
        
        assert "h*0.85" in filter_str  # Bottom position
    
    def test_text_filter_escapes_special_chars(self):
        """Test that special characters are escaped."""
        from app.utils.ffmpeg import _build_text_filter, TextOverlay
        
        overlay = TextOverlay(
            text="Test: with colons",
            position="center"
        )
        
        filter_str = _build_text_filter(overlay, 30.0)
        
        # Colons should be escaped
        assert "\\:" in filter_str
    
    def test_scale_filter_vertical(self):
        """Test vertical preset scale filter."""
        from app.utils.ffmpeg import _build_scale_filter, ExportPreset
        
        preset = ExportPreset.vertical()
        filter_str = _build_scale_filter(preset, 1920, 1080)
        
        assert "1080" in filter_str
        assert "1920" in filter_str
        assert "scale" in filter_str
        assert "pad" in filter_str
    
    def test_scale_filter_original(self):
        """Test original preset returns empty filter."""
        from app.utils.ffmpeg import _build_scale_filter, ExportPreset
        
        preset = ExportPreset.original()
        filter_str = _build_scale_filter(preset, 1920, 1080)
        
        assert filter_str == ""
    
    def test_export_preset_vertical_values(self):
        """Test vertical preset has correct values."""
        from app.utils.ffmpeg import ExportPreset
        from app.config import settings
        
        preset = ExportPreset.vertical()
        
        assert preset.name == "vertical"
        assert preset.width == settings.vertical_width
        assert preset.height == settings.vertical_height
        assert preset.fps == settings.vertical_fps


class TestMetadataGeneration:
    """Tests for metadata.json generation."""
    
    def test_metadata_structure(self):
        """Test generated metadata has correct structure."""
        from app.services.publish_service import PublishService
        from app.models.clip import Clip
        from app.models.niche import Niche
        from app.models.account import Account, Platform, AuthStatus
        
        # Create mock objects
        clip = Clip(
            id=1,
            project_id=1,
            start_time=0,
            end_time=30,
            name="Test Clip"
        )
        
        niche = Niche(
            id=1,
            name="Sports",
            default_hashtags=json.dumps(["sports"])
        )
        
        account = Account(
            id=1,
            niche_id=1,
            platform=Platform.YOUTUBE_SHORTS,
            handle="@test",
            auth_status=AuthStatus.CONNECTED
        )
        
        # Create service (with mock db)
        service = PublishService(None)
        
        metadata = service._generate_metadata(
            clip=clip,
            niche=niche,
            platform=Platform.YOUTUBE_SHORTS,
            accounts=[account],
            caption="Test caption",
            hashtags=["test"],
            output_filename="test.mp4"
        )
        
        # Check structure
        assert "generated_at" in metadata
        assert "clip" in metadata
        assert "niche" in metadata
        assert "platform" in metadata
        assert "accounts" in metadata
        assert "content" in metadata
        assert "output" in metadata
        
        # Check clip info
        assert metadata["clip"]["id"] == 1
        assert metadata["clip"]["name"] == "Test Clip"
        
        # Check content
        assert "caption" in metadata["content"]
        assert "hashtags" in metadata["content"]
        assert "hashtag_string" in metadata["content"]
