"""
AfriMine AI — CrewAI Multi-Agent Orchestrator
Wraps all 6 agents into a CrewAI crew for coordinated task execution.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from crewai import Agent, Task, Crew, Process
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logger.warning("CrewAI not installed — using direct agent orchestration")

# crewAI v2 uses LiteLLM for LLM routing; langchain_google_genai is no longer required
LITELLM_AVAILABLE = False
try:
    import litellm  # noqa: F401 — crewai uses this internally
    LITELLM_AVAILABLE = True
except ImportError:
    pass


def create_crew(
    gemini_api_key: str = "",
    gemini_model: str = "gemini-1.5-flash",
    verbose: bool = True,
) -> Crew | None:
    """
    Create and configure the AfriMine AI CrewAI crew with all 6 agents.

    Returns a Crew object if CrewAI is installed, None otherwise.
    """
    if not CREWAI_AVAILABLE:
        logger.warning("CrewAI not available. Use AnalysisPipeline for direct orchestration.")
        return None

    # Configure LLM for agents
    # crewAI v2 uses LiteLLM — pass model as "provider/model" string
    llm = None
    if gemini_api_key:
        try:
            # crewAI v2 accepts llm as a string (LiteLLM format) or model config
            import os
            os.environ["GOOGLE_API_KEY"] = gemini_api_key
            # Use "gemini/gemini-1.5-flash" LiteLLM format for crewAI v2
            llm = f"gemini/{gemini_model}"
            logger.info(f"CrewAI LLM configured: {llm}")
        except Exception as e:
            logger.warning(f"Failed to configure LLM for crewAI: {e}")
    elif LITELLM_AVAILABLE:
        # Try without API key (environment may have it pre-configured)
        llm = f"gemini/{gemini_model}"

    # ── Define 6 Agents (crewAI v2 compatible) ──

    sampling_agent = Agent(
        role="Field Sampling Planner",
        goal="Plan optimal mineral sampling routes across Kenya's diverse terrain",
        backstory=(
            "You are an experienced field geologist who has planned sampling campaigns "
            "across Kenya's Rift Valley, Coastal region, and Western greenstone belts. "
            "You understand terrain accessibility, seasonal weather patterns, and how to "
            "maximize sample coverage within budget constraints."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    analysis_agent = Agent(
        role="Mineral Identification Specialist",
        goal="Accurately classify minerals from images and estimate their grade",
        backstory=(
            "You are a mineralogist specializing in optical mineralogy and XRF analysis. "
            "You can identify 20+ mineral species from hand specimen photos and correlate "
            "visual features with chemical composition. You understand Kenya's mineral "
            "assemblages and can distinguish economically significant minerals from waste."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    geology_agent = Agent(
        role="Geological Interpreter",
        goal="Interpret mineral findings within Kenya's geological framework",
        backstory=(
            "You are a structural geologist with deep knowledge of Kenya's geological "
            "provinces: the Mozambique Belt, Nyanza Craton, East African Rift, and "
            "Coastal Sedimentary Basin. You can correlate mineral assemblages with "
            "tectonic settings, metamorphic grade, and mineralization styles."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    market_agent = Agent(
        role="Commodity Market Analyst",
        goal="Track mineral prices and evaluate economic viability of deposits",
        backstory=(
            "You are a mining economist who tracks global commodity markets and "
            "understands the economics of small-scale mining in East Africa. "
            "You can calculate break-even grades, profit margins, and compare "
            "investment returns across different mineral commodities."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    report_agent = Agent(
        role="Report Generation Specialist",
        goal="Generate comprehensive, professional mineral analysis reports",
        backstory=(
            "You are a technical writer who produces clear, actionable reports for "
            "mining stakeholders. You combine geological data, market analysis, and "
            "compliance information into documents suitable for investors, regulators, "
            "and community leaders. Reports are accessible to non-technical audiences."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    compliance_agent = Agent(
        role="Regulatory Compliance Specialist",
        goal="Ensure all mining activities comply with Kenya's Mining Act 2016",
        backstory=(
            "You are a mining lawyer specializing in Kenya's Mining Act 2016 and "
            "environmental regulations (EMCA 1999). You advise artisanal and "
            "small-scale miners on licensing, environmental impact assessments, "
            "royalty payments, and community development agreements."
        ),
        verbose=verbose,
        llm=llm,
        allow_delegation=False,
        max_iter=15,
    )

    return Crew(
        agents=[sampling_agent, analysis_agent, geology_agent, market_agent, report_agent, compliance_agent],
        verbose=verbose,
        process=Process.sequential,
    )


def create_tasks(crew: Crew, input_data: dict) -> list[Task]:
    """Create tasks for the crew based on input data."""
    if not CREWAI_AVAILABLE:
        return []

    tasks = []

    # Task 1: Sampling Plan
    tasks.append(Task(
        description=(
            f"Plan a mineral sampling campaign for the area of interest:\n"
            f"- County: {input_data.get('county', 'Unknown')}\n"
            f"- Area bounds: ({input_data.get('lat_min', 0)}, {input_data.get('lon_min', 0)}) "
            f"to ({input_data.get('lat_max', 0)}, {input_data.get('lon_max', 0)})\n"
            f"- Grid spacing: {input_data.get('spacing_m', 500)}m\n"
            f"Generate a sampling grid, prioritize points by geological potential, "
            f"and optimize the field route for efficiency."
        ),
        expected_output="A complete sampling plan with grid coordinates, priorities, and daily route schedule.",
        agent=crew.agents[0],
    ))

    # Task 2: Mineral Analysis
    tasks.append(Task(
        description=(
            f"Analyze mineral samples from {input_data.get('county', 'Unknown')} County.\n"
            f"Number of samples: {input_data.get('n_samples', 'unknown')}\n"
            f"Classify each sample's mineral type, estimate grade, and assess confidence.\n"
            f"Consider Kenya's typical mineral assemblages for the geological province."
        ),
        expected_output="Classification results for each sample with mineral type, confidence, grade estimate, and value score.",
        agent=crew.agents[1],
    ))

    # Task 3: Geological Interpretation
    tasks.append(Task(
        description=(
            f"Provide geological context for the mineral findings in {input_data.get('county', 'Unknown')} County.\n"
            f"Identify the geological province, interpret mineral associations, "
            f"estimate depth and extent of mineralization, and suggest exploration vectors."
        ),
        expected_output="Geological interpretation report with province identification, mineral associations, and exploration recommendations.",
        agent=crew.agents[2],
    ))

    # Task 4: Market Analysis
    tasks.append(Task(
        description=(
            "Evaluate the economic viability of the identified mineral deposits.\n"
            "Provide current commodity prices, calculate profit margins, "
            "and compare the deposit economics across identified minerals."
        ),
        expected_output="Market analysis with commodity prices, economic viability assessment, and investment recommendations.",
        agent=crew.agents[3],
    ))

    # Task 5: Report Generation
    tasks.append(Task(
        description=(
            "Compile all findings into a comprehensive mineral analysis report.\n"
            "Include executive summary, methodology, results, economic evaluation, "
            "and recommendations. Make it accessible to both technical and non-technical audiences."
        ),
        expected_output="A complete, professional mineral analysis report in text format suitable for PDF generation.",
        agent=crew.agents[4],
    ))

    # Task 6: Compliance Check
    tasks.append(Task(
        description=(
            f"Check regulatory compliance for a mining operation in {input_data.get('county', 'Unknown')} County.\n"
            f"Operation type: {input_data.get('licence_type', 'exploration_licence')}\n"
            f"Verify licence requirements, environmental compliance, safety standards, "
            f"royalty obligations, and community development requirements under Kenya's Mining Act 2016."
        ),
        expected_output="Compliance report with status checks, action items, and permit requirements.",
        agent=crew.agents[5],
    ))

    return tasks


def run_crew(input_data: dict, gemini_api_key: str = "", gemini_model: str = "gemini-1.5-flash") -> dict:
    """
    Convenience function to create and run the complete crew.
    Falls back to direct orchestration if CrewAI is not available.
    """
    crew = create_crew(gemini_api_key, gemini_model)
    if crew is None:
        # Fallback to direct pipeline
        from pipelines.analysis_pipeline import AnalysisPipeline
        from utils.config import AfriMineConfig

        config = AfriMineConfig()
        config.agents.gemini_api_key = gemini_api_key
        config.agents.gemini_model = gemini_model

        pipeline = AnalysisPipeline(config)
        return pipeline.run_full_pipeline(
            area=input_data,
            sample_images=input_data.get("sample_images", []),
            miner_info=input_data.get("miner_info"),
            licence_type=input_data.get("licence_type", "exploration_licence"),
        )

    tasks = create_tasks(crew, input_data)
    crew.tasks = tasks
    result = crew.kickoff()

    return {
        "crew_result": str(result),
        "status": "completed",
    }
