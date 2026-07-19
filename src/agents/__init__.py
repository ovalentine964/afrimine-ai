"""
AfriMine AI — Agent Pipeline Package
======================================

Production LangGraph 1.0 pipeline for mineral analysis.

6 Agents:
    1. Sampling — GPS waypoints and field routes
    2. Analysis — Mineral classification (Gemini 2.5 Flash vision)
    3. Geology — Geological interpretation (Migori Belt RAG)
    4. Market — Price data and NPV calculation
    5. Report — Investor PDF generation
    6. Compliance — Kenya Mining Act 2016 validation

Quick start:
    from main import AfriMinePipeline
    pipeline = AfriMinePipeline()
    result = await pipeline.analyze(location, sample_data, user_id)
"""

__version__ = "1.0.0"
