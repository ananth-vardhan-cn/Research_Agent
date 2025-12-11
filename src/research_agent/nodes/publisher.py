"""Publisher node for finalizing and publishing reports."""

import structlog
from datetime import datetime
from typing import List, Dict

from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchState, FinalReport, DraftSection, Source

logger = structlog.get_logger()


async def publisher_node(state: ResearchState, gemini_client: GeminiClient) -> ResearchState:
    """Finalize and publish the research report.
    
    Args:
        state: Current research state
        gemini_client: Gemini LLM client
        
    Returns:
        Updated state with final report
    """
    logger.info("publisher_node_start")
    
    draft_sections = state.get("draft_sections", [])
    source_map = state.get("source_map", {})
    task = state.get("task")
    
    if not draft_sections:
        return {"error": "No draft sections to publish"}
    
    # format sources
    references = list(source_map.keys())
    
    # Create references section
    references_content = "# References\n\n"
    for source_id in references:
        source = source_map.get(source_id)
        if source:
            references_content += f"- **{source.title}**: {source.url}\n"
        else:
            references_content += f"- [{source_id}]\n"
            
    # Create a copy of draft sections to avoid modifying state in place unexpectedly
    final_sections = [s.model_copy() for s in draft_sections]
    
    # Add references section
    final_sections.append(
        DraftSection(
            title="References",
            content=references_content,
            sources=[],
            order=len(final_sections)
        )
    )
    
    # Create final report object
    final_report = FinalReport(
        title=task.query if task else "Research Report",
        sections=final_sections,
        references=references,
        created_at=datetime.now()
    )
    
    # We could generate a nicely formatted markdown string here and save it to a file or field
    # But the state model stores the structure.
    
    logger.info("publisher_node_complete", sections=len(draft_sections), references=len(references))
    
    return {
        "final_report": final_report,
        # Clear previous feedback if any
        "user_feedback": None 
    }
