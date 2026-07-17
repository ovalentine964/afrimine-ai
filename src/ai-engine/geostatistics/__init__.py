"""
AfriMine AI — Geostatistics Engine
===================================

Grade estimation and resource classification for Kenyan mining families.

Modules:
    variogram            – Empirical/theoretical variogram analysis
    kriging              – Ordinary, Universal & Block Kriging
    grade_estimation     – Log-normal handling, top-cutting, compositing
    block_model          – 3D block model generation
    resource_classification – JORC/SAMREC classification rules
"""

from .variogram import VariogramAnalysis
from .kriging import KrigingEngine
from .grade_estimation import GradeEstimator
from .block_model import BlockModel
from .resource_classification import ResourceClassifier

__all__ = [
    "VariogramAnalysis",
    "KrigingEngine",
    "GradeEstimator",
    "BlockModel",
    "ResourceClassifier",
]

__version__ = "0.1.0"
