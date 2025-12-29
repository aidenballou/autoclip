# V2 Pipeline - Highlight-aware clip generation
"""
V2 Pipeline: Highlight-Aware Clip Generation

This pipeline replaces simple scene-cut segmentation with a multi-stage
approach that identifies meaningful highlight moments and selects natural
clip boundaries.

Pipeline stages:
1. Feature Extraction: Audio loudness, motion activity, scene cuts, fades
2. Anchor Detection: Find likely highlight moments from excitement signals
3. Boundary Scoring: Score natural clip boundary candidates
4. Window Selection: Choose start/end by snapping to best boundaries
5. Post-filtering: Remove overlap, duplicates, boring clips

All modules are designed to work with local signals only (no ML models).
"""

__version__ = "2.0.0"

from .runner import run_v2_pipeline

__all__ = ["run_v2_pipeline", "__version__"]

