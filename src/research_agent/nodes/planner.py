"""Planner node implementing STORM methodology."""

import structlog

from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import Perspective, Plan, ResearchState, Section

logger = structlog.get_logger()


PLANNER_SYSTEM_INSTRUCTION = """You are an expert research planner using the STORM (Synthesis of Topic Outline through Retrieval and Multi-perspective question asking) methodology.

Your task is to:
1. Mine diverse perspectives on the research topic
2. Generate a hierarchical outline with sections and subsections
3. Identify dependencies between sections
4. Specify required source types for each section
5. Create a detailed research plan with clear steps
6. Provide visible thinking and reasoning for your decisions

Be thorough, structured, and consider multiple angles for comprehensive research."""


async def planner_node(state: ResearchState, gemini_client: GeminiClient) -> ResearchState:
    """Plan research using STORM methodology.
    
    This node:
    - Mines multiple perspectives on the topic
    - Generates hierarchical outline with dependencies
    - Creates detailed research plan
    - Logs visible thinking
    
    Args:
        state: Current research state
        gemini_client: Gemini LLM client
        
    Returns:
        Updated state with plan and perspectives
    """
    logger.info("planner_node_start", query=state["task"].query)
    
    task = state["task"]
    query = task.query
    context = task.context or ""
    
    thinking_log: list[str] = []
    
    # Step 1: Mine perspectives using STORM
    logger.info("mining_perspectives")
    thinking_log.append("Step 1: Mining diverse perspectives on the topic")
    
    perspectives_prompt = f"""Research Query: {query}
{f"Context: {context}" if context else ""}

Using the STORM methodology, identify 4-6 diverse perspectives or angles for researching this topic.
Each perspective should represent a different viewpoint, stakeholder, or dimension of analysis.

For each perspective, provide:
- A clear name
- A detailed description
- 3-5 key focus areas to explore

Provide your thinking process, then output in JSON format:
{{
    "thinking": "Your reasoning about the perspectives...",
    "perspectives": [
        {{
            "name": "perspective name",
            "description": "detailed description",
            "focus_areas": ["area1", "area2", "area3"]
        }}
    ]
}}"""
    
    perspectives_response = await gemini_client.generate_structured(
        prompt=perspectives_prompt,
        system_instruction=PLANNER_SYSTEM_INSTRUCTION,
    )
    
    thinking_log.append(perspectives_response.get("thinking", "Perspectives identified"))
    
    perspectives = [
        Perspective(**p) for p in perspectives_response.get("perspectives", [])
    ]
    
    logger.info("perspectives_mined", count=len(perspectives))
    
    # Step 2: Generate hierarchical outline
    logger.info("generating_outline")
    thinking_log.append("Step 2: Creating hierarchical outline with dependencies")
    
    outline_prompt = f"""Research Query: {query}
{f"Context: {context}" if context else ""}

Perspectives identified:
{chr(10).join(f"- {p.name}: {p.description}" for p in perspectives)}

Create a hierarchical outline for a comprehensive research report. For each section:
- Provide a clear title and description
- List 2-4 subsections
- Identify dependencies (which sections must be completed first)
- Specify required source types (e.g., "academic papers", "industry reports", "news articles")
- Map to relevant perspectives

The outline should have 5-8 main sections covering the topic comprehensively.

Provide your thinking process, then output in JSON format:
{{
    "thinking": "Your reasoning about the outline structure...",
    "outline": [
        {{
            "title": "section title",
            "description": "section description",
            "subsections": ["subsection1", "subsection2"],
            "dependencies": ["title of section this depends on"],
            "required_sources": ["source type1", "source type2"],
            "perspectives": ["perspective name1", "perspective name2"]
        }}
    ]
}}"""
    
    outline_response = await gemini_client.generate_structured(
        prompt=outline_prompt,
        system_instruction=PLANNER_SYSTEM_INSTRUCTION,
    )
    
    thinking_log.append(outline_response.get("thinking", "Outline generated"))
    
    outline = [Section(**s) for s in outline_response.get("outline", [])]
    
    logger.info("outline_generated", sections=len(outline))
    
    # Step 3: Create detailed research plan
    logger.info("creating_research_plan")
    thinking_log.append("Step 3: Developing detailed research plan with execution steps")
    
    plan_prompt = f"""Research Query: {query}

Outline sections:
{chr(10).join(f"{i+1}. {s.title} - {s.description}" for i, s in enumerate(outline))}

Create a detailed research plan with specific, actionable steps. Each step should:
- Have a clear description
- Be mapped to a perspective (if applicable)
- Specify dependencies on other steps
- Have an estimated time in seconds

Create 8-15 steps that will execute the research plan efficiently.

Provide your thinking process, then output in JSON format:
{{
    "thinking": "Your reasoning about the research plan execution...",
    "title": "comprehensive title for the research plan",
    "steps": [
        {{
            "step_number": 1,
            "description": "step description",
            "perspective": "perspective name or null",
            "dependencies": [step numbers this depends on],
            "estimated_time": 300
        }}
    ]
}}"""
    
    plan_response = await gemini_client.generate_structured(
        prompt=plan_prompt,
        system_instruction=PLANNER_SYSTEM_INSTRUCTION,
    )
    
    thinking_log.append(plan_response.get("thinking", "Research plan created"))
    
    # Build the plan
    plan = Plan(
        title=plan_response.get("title", f"Research Plan: {query}"),
        outline=outline,
        steps=plan_response.get("steps", []),
        perspectives=[p.name for p in perspectives],
        thinking_log=thinking_log,
    )
    
    logger.info(
        "planner_node_complete",
        perspectives_count=len(perspectives),
        sections_count=len(outline),
        steps_count=len(plan.steps),
    )
    
    # Update state
    return {
        "perspectives": perspectives,
        "plan": plan,
        "awaiting_approval": True,
    }
