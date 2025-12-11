"""Writer node for drafting report sections."""

import asyncio
import structlog
from typing import List, Optional

from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchState, DraftSection, Section, ResearchData

logger = structlog.get_logger()


WRITER_SYSTEM_INSTRUCTION = """You are an expert academic research writer. 
Your goal is to synthesize a comprehensive, high-quality research report based on the provided research data and outline.

GUIDELINES:
1.  **Content**: Synthesize information from the provided research data. Do not invent facts.
2.  **Structure**: Follow the provided section outline exactly.
3.  **Flow**: Ensure smooth transitions between sections. weave "contextual glue" to connect ideas.
4.  **Citations**: rigorously cite every factual claim using the format `[source_id]`. 
    - Example: "The market grew by 5% [source_123]."
    - If multiple sources support a claim: "The market grew by 5% [source_123, source_456]."
    - ONLY use source_ids provided in the research data.
5.  **Tone**: Professional, objective, and analytical.
6.  **Length**: Aim for depth and detail.

When revising based on critique:
- Address every issue raised in the critique.
- Improve the content while maintaining the structure.
"""


async def writer_node(state: ResearchState, gemini_client: GeminiClient) -> ResearchState:
    """Draft report sections from research data.
    
    Args:
        state: Current research state
        gemini_client: Gemini LLM client
        
    Returns:
        Updated state with draft sections
    """
    logger.info("writer_node_start")
    
    plan = state.get("plan")
    if not plan or not plan.outline:
        logger.error("no_plan_or_outline_found")
        return {"error": "No research plan or outline found."}
    
    research_data = state.get("research_data", [])
    critique = state.get("critique")
    user_feedback = state.get("user_feedback")

    if user_feedback:
        # Treat user feedback as high priority critique
        from research_agent.models.state import Critique
        critique = Critique(
            issues=[f"User Feedback: {user_feedback}"],
            suggestions=["Address user feedback"],
            severity="high"
        )
    
    # Prepare research data context
    # Format: [source_id] (perspective) Content...
    data_context = _format_research_data(research_data)
    
    draft_sections: List[DraftSection] = []
    
    # Iterate through sections
    # We will generate sections sequentially to maintain flow
    previous_section_content = ""
    
    for i, section in enumerate(plan.outline):
        logger.info("drafting_section", section=section.title, index=i)
        
        section_content = await _draft_section(
            section=section,
            index=i,
            total_sections=len(plan.outline),
            previous_content_summary=previous_section_content[-2000:] if previous_section_content else "", # Pass last part of prev section for context
            data_context=data_context,
            critique=critique if state.get("revision_count", 0) > 0 else None,
            gemini_client=gemini_client
        )
        
        draft_sections.append(
            DraftSection(
                title=section.title,
                content=section_content,
                sources=_extract_sources(section_content),
                order=i
            )
        )
        
        previous_section_content = section_content
        
    logger.info("writer_node_complete", sections_generated=len(draft_sections))
    
    return {
        "draft_sections": draft_sections,
        # Clear critique after addressing it
        "critique": None, 
    }


def _format_research_data(research_data: List[ResearchData]) -> str:
    """Format research data for context window."""
    formatted = []
    for item in research_data:
        # Truncate very long content if necessary, but Gemini has large context.
        # Let's keep it reasonable.
        content_preview = item.content[:5000] 
        formatted.append(f"SOURCE_ID: {item.source_id}\nPERSPECTIVE: {item.perspective}\nCONTENT:\n{content_preview}\n---")
    return "\n".join(formatted)


async def _draft_section(
    section: Section,
    index: int,
    total_sections: int,
    previous_content_summary: str,
    data_context: str,
    critique: Optional[object],
    gemini_client: GeminiClient
) -> str:
    """Draft a single section."""
    
    prompt = f"""
SECTION TO DRAFT: {section.title}
DESCRIPTION: {section.description}
SUBSECTIONS: {', '.join(section.subsections)}

CONTEXT FROM PREVIOUS SECTION (for flow):
...{previous_content_summary}

RESEARCH DATA:
{data_context}
"""

    if critique:
        prompt += f"\n\nCRITIQUE TO ADDRESS:\nIssues: {', '.join(critique.issues)}\nSuggestions: {', '.join(critique.suggestions)}\n"
        prompt += "\nPlease revise or draft this section paying special attention to the above critique."

    prompt += f"\n\nDraft the section '{section.title}'. Ensure you cover all subsections. Cite sources using [source_id]. Return ONLY the markdown content for this section."

    response = await gemini_client.generate(
        prompt=prompt,
        system_instruction=WRITER_SYSTEM_INSTRUCTION
    )
    
    return response


def _extract_sources(content: str) -> List[str]:
    """Extract source IDs from content."""
    import re
    # Match [source_id] or [source_id, source_id2]
    # Simple regex for now
    sources = set()
    matches = re.findall(r'\[(.*?)\]', content)
    for match in matches:
        # split by comma if multiple sources
        ids = [s.strip() for s in match.split(',')]
        for source_id in ids:
            # Basic validation to avoid false positives (e.g. [1]) unless source_ids look like that.
            # Assuming source_ids are strings from the system.
            if "source" in source_id or "_" in source_id: # Heuristic
                 sources.add(source_id)
            elif len(source_id) > 1: # Capture other potential IDs
                 sources.add(source_id)
                 
    return list(sources)
