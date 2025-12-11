"""Research Manager node for coordinating research execution."""

import uuid
from datetime import datetime
from typing import Optional

import structlog

from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import GapAnalysis, ResearchState, WorkPackage

logger = structlog.get_logger()


MANAGER_SYSTEM_INSTRUCTION = """You are an expert research manager responsible for:
1. Breaking down research plans into parallelizable work packages
2. Tracking dependencies and coordinating execution
3. Analyzing research gaps and determining if more research is needed
4. Deciding when to advance from research to writing phase

Be strategic, efficient, and ensure comprehensive coverage of the research topic."""


async def research_manager_node(
    state: ResearchState, gemini_client: GeminiClient
) -> ResearchState:
    """Manage research execution and coordinate workers.
    
    This node:
    - Breaks plan into parallelizable work packages
    - Tracks dependencies
    - Performs gap analysis
    - Decides whether to spawn more research or advance to writing
    
    Args:
        state: Current research state
        gemini_client: Gemini LLM client
        
    Returns:
        Updated state with work packages and next action
    """
    logger.info("research_manager_node_start")
    
    plan = state.get("plan")
    if not plan:
        logger.error("no_plan_available")
        return {"error": "No research plan available"}
    
    research_wave = state.get("research_wave", 0)
    existing_packages = state.get("work_packages", [])
    research_data = state.get("research_data", [])
    
    logger.info(
        "manager_state",
        wave=research_wave,
        existing_packages=len(existing_packages),
        research_data_count=len(research_data),
    )
    
    # Check if this is the first wave or a reflexion wave
    is_first_wave = research_wave == 0
    
    if is_first_wave:
        # First wave: Create work packages from plan
        logger.info("creating_initial_work_packages")
        
        work_packages_prompt = f"""Research Plan: {plan.title}

Outline sections:
{chr(10).join(f"- {s.title}: {s.description}" for s in plan.outline)}

Perspectives:
{chr(10).join(f"- {p}" for p in plan.perspectives)}

Create parallelizable work packages for research workers. Each package should:
- Target a specific section or subsection
- Include 3-5 focused search queries
- Map to a relevant perspective
- Specify dependencies on other packages (by package ID)

Generate 6-12 work packages that cover all sections comprehensively.

Provide your reasoning, then output in JSON format:
{{
    "thinking": "Your strategy for breaking down the research...",
    "packages": [
        {{
            "section_title": "section title",
            "queries": ["query1", "query2", "query3"],
            "perspective": "perspective name or null",
            "dependencies": []
        }}
    ]
}}"""
        
        packages_response = await gemini_client.generate_structured(
            prompt=work_packages_prompt,
            system_instruction=MANAGER_SYSTEM_INSTRUCTION,
        )
        
        logger.info(
            "work_packages_created",
            thinking=packages_response.get("thinking", ""),
        )
        
        # Create work packages
        packages = []
        for pkg_data in packages_response.get("packages", []):
            package = WorkPackage(
                package_id=str(uuid.uuid4()),
                section_title=pkg_data["section_title"],
                queries=pkg_data["queries"],
                perspective=pkg_data.get("perspective"),
                dependencies=pkg_data.get("dependencies", []),
                status="pending",
                assigned_at=datetime.now(),
            )
            packages.append(package)
        
        logger.info("initial_packages_created", count=len(packages))
        
        # No gap analysis on first wave
        gap_analysis: Optional[GapAnalysis] = None
        
    else:
        # Reflexion wave: Analyze gaps and decide on next steps
        logger.info("performing_gap_analysis")
        
        completed_packages = [p for p in existing_packages if p.status == "completed"]
        
        gap_analysis_prompt = f"""Research Plan: {plan.title}

Outline sections:
{chr(10).join(f"- {s.title}" for s in plan.outline)}

Required perspectives:
{chr(10).join(f"- {p}" for p in plan.perspectives)}

Completed work packages: {len(completed_packages)}
Research data collected: {len(research_data)}

Research data summary:
{chr(10).join(f"- {rd.source_id}: {rd.content[:100]}..." for rd in research_data[:10])}

Analyze the research collected so far and identify:
1. Missing perspectives that haven't been adequately covered
2. Missing source types needed for sections
3. Sections that need more depth or breadth
4. Overall confidence in completeness (0.0 to 1.0)
5. Whether more research is needed before writing

Provide detailed analysis, then output in JSON format:
{{
    "thinking": "Your analysis of research gaps...",
    "missing_perspectives": ["perspective1", "perspective2"],
    "missing_sources": ["source type1", "source type2"],
    "incomplete_sections": ["section1", "section2"],
    "confidence_score": 0.75,
    "needs_more_research": true
}}"""
        
        gap_response = await gemini_client.generate_structured(
            prompt=gap_analysis_prompt,
            system_instruction=MANAGER_SYSTEM_INSTRUCTION,
        )
        
        logger.info(
            "gap_analysis_complete",
            thinking=gap_response.get("thinking", ""),
            confidence=gap_response.get("confidence_score", 0.0),
        )
        
        gap_analysis = GapAnalysis(
            missing_perspectives=gap_response.get("missing_perspectives", []),
            missing_sources=gap_response.get("missing_sources", []),
            incomplete_sections=gap_response.get("incomplete_sections", []),
            confidence_score=gap_response.get("confidence_score", 0.0),
            needs_more_research=gap_response.get("needs_more_research", False),
        )
        
        # If more research needed, create additional packages
        if gap_analysis.needs_more_research:
            logger.info("creating_additional_work_packages")
            
            additional_packages_prompt = f"""Based on the gap analysis:

Missing perspectives: {', '.join(gap_analysis.missing_perspectives)}
Missing sources: {', '.join(gap_analysis.missing_sources)}
Incomplete sections: {', '.join(gap_analysis.incomplete_sections)}

Create 3-6 targeted work packages to address these gaps.

Output in JSON format:
{{
    "thinking": "Strategy for addressing gaps...",
    "packages": [
        {{
            "section_title": "section title",
            "queries": ["query1", "query2", "query3"],
            "perspective": "perspective name or null",
            "dependencies": []
        }}
    ]
}}"""
            
            additional_response = await gemini_client.generate_structured(
                prompt=additional_packages_prompt,
                system_instruction=MANAGER_SYSTEM_INSTRUCTION,
            )
            
            packages = []
            for pkg_data in additional_response.get("packages", []):
                package = WorkPackage(
                    package_id=str(uuid.uuid4()),
                    section_title=pkg_data["section_title"],
                    queries=pkg_data["queries"],
                    perspective=pkg_data.get("perspective"),
                    dependencies=pkg_data.get("dependencies", []),
                    status="pending",
                    assigned_at=datetime.now(),
                )
                packages.append(package)
            
            logger.info("additional_packages_created", count=len(packages))
        else:
            logger.info("research_complete_advancing_to_writing")
            packages = []
    
    logger.info(
        "research_manager_node_complete",
        new_packages=len(packages),
        gap_analysis_available=gap_analysis is not None,
    )
    
    # Update state
    result: ResearchState = {
        "work_packages": existing_packages + packages,
        "research_wave": research_wave + 1,
    }
    
    if gap_analysis:
        result["gap_analysis"] = gap_analysis
    
    return result
