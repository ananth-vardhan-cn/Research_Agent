"""Reviewer node for critiquing draft reports."""

import structlog
import re
from typing import List, Set

from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchState, Critique, DraftSection

logger = structlog.get_logger()

REVIEWER_SYSTEM_INSTRUCTION = """You are an expert research reviewer and critic.
Your job is to evaluate the draft report for quality, accuracy, and completeness.

Perform a Self-RAG loop:
1.  **Retrieval Grader**: Are the citations accurate?
2.  **Hallucination Grader**: Are the claims supported by the cited sources?
3.  **Answer Grader**: Does the report fully answer the research query and follow the outline?

Provide a structured critique with specific issues and actionable suggestions.
Assign a severity level: low, medium, or high.
"""


async def reviewer_node(state: ResearchState, gemini_client: GeminiClient) -> ResearchState:
    """Review and critique draft report.
    
    Args:
        state: Current research state
        gemini_client: Gemini LLM client
        
    Returns:
        Updated state with critique
    """
    logger.info("reviewer_node_start")
    
    draft_sections = state.get("draft_sections", [])
    source_map = state.get("source_map", {})
    task = state.get("task")
    plan = state.get("plan")
    
    if not draft_sections:
        logger.error("no_draft_sections_found")
        return {"error": "No draft sections found to review."}
        
    # Combine sections for review
    full_text = "\n\n".join([f"# {s.title}\n\n{s.content}" for s in draft_sections])
    
    # 1. Deterministic Validation (Regex & Source Map)
    validation_issues = _validate_citations(full_text, source_map)
    
    # 2. LLM Critique (Self-RAG & Quality)
    prompt = f"""
RESEARCH QUERY: {task.query if task else 'Unknown'}

OUTLINE:
{chr(10).join([f"- {s.title}: {s.description}" for s in plan.outline]) if plan else 'Unknown'}

DRAFT REPORT:
{full_text[:50000]}  # Truncate if necessary, though Gemini handles large context

PRE-COMPUTED VALIDATION ISSUES:
{chr(10).join(validation_issues)}

Review the draft report above. 
1. Identify any gaps in the content regarding the research query.
2. Check for logical flow and coherence.
3. Assess the quality of writing and tone.
4. Verify if the validation issues mentioned above are critical.

Provide your output in JSON format:
{{
    "issues": ["issue 1", "issue 2"],
    "suggestions": ["suggestion 1", "suggestion 2"],
    "severity": "low|medium|high"
}}
"""

    response = await gemini_client.generate_structured(
        prompt=prompt,
        system_instruction=REVIEWER_SYSTEM_INSTRUCTION
    )
    
    # Merge validation issues with LLM issues
    issues = response.get("issues", [])
    suggestions = response.get("suggestions", [])
    severity = response.get("severity", "medium")
    
    if validation_issues:
        issues.extend(validation_issues)
        # If there are missing sources, severity should be at least medium
        if any("Missing source definition" in i for i in validation_issues):
            if severity == "low":
                severity = "medium"

    critique = Critique(
        issues=issues,
        suggestions=suggestions,
        severity=severity
    )
    
    revision_count = state.get("revision_count", 0) + 1
    
    logger.info("reviewer_node_complete", severity=severity, issues_count=len(issues))
    
    return {
        "critique": critique,
        "revision_count": revision_count
    }


def _validate_citations(text: str, source_map: dict) -> List[str]:
    """Validate citations in text against source map."""
    issues = []
    
    # Extract all [source_id] patterns
    # Handles [source_1], [source_1, source_2]
    matches = re.findall(r'\[(.*?)\]', text)
    found_sources = set()
    
    for match in matches:
        ids = [s.strip() for s in match.split(',')]
        for source_id in ids:
            # Heuristic to filter out non-citations like [1] unless they match source map
            if source_id in source_map:
                found_sources.add(source_id)
            elif "source" in source_id: # Likely a citation attempt
                 if source_id not in source_map:
                     issues.append(f"Missing source definition for citation: [{source_id}]")
            # Else ignore (might be other markdown usage)
            
    if not found_sources:
         issues.append("No valid citations found in the text.")
         
    return issues
