"""Example: Run the research graph with HITL approval."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from research_agent.config import get_settings
from research_agent.graph import create_research_graph
from research_agent.logging_config import setup_logging
from research_agent.models.state import ResearchState, Task

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


async def main() -> None:
    """Run research graph example."""
    # Setup
    settings = get_settings()
    setup_logging(settings.logging)
    
    # Create graph
    graph = create_research_graph(settings)
    compiled_graph = graph.compile()
    
    # Create initial state
    initial_state: ResearchState = {
        "task": Task(
            query="What are the latest developments in quantum computing?",
            context="Focus on practical applications and recent breakthroughs.",
        ),
        "perspectives": [],
        "research_wave": 0,
        "work_packages": [],
        "research_data": [],
        "source_map": {},
        "draft_sections": [],
        "visit_history": [],
        "revision_count": 0,
        "awaiting_approval": False,
    }
    
    print("\n" + "="*80)
    print("RESEARCH AGENT - PLANNER & MANAGER DEMO")
    print("="*80)
    print(f"\nQuery: {initial_state['task'].query}")
    print(f"Context: {initial_state['task'].context}")
    print("\n" + "="*80 + "\n")
    
    # Run planner node
    print("▶ Running Planner Node (STORM methodology)...")
    try:
        config = {"configurable": {"thread_id": "demo-thread"}}
        result = await compiled_graph.ainvoke(initial_state, config)
        
        print("\n✓ Planner completed!")
        
        # Display perspectives
        if result.get("perspectives"):
            print(f"\n📊 Perspectives Identified ({len(result['perspectives'])}):")
            for i, p in enumerate(result["perspectives"], 1):
                print(f"\n  {i}. {p.name}")
                print(f"     {p.description}")
                print(f"     Focus areas: {', '.join(p.focus_areas[:3])}")
        
        # Display outline
        if result.get("plan") and result["plan"].outline:
            print(f"\n📋 Research Outline ({len(result['plan'].outline)} sections):")
            for i, section in enumerate(result["plan"].outline, 1):
                print(f"\n  {i}. {section.title}")
                print(f"     {section.description}")
                if section.subsections:
                    print(f"     Subsections: {', '.join(section.subsections[:2])}")
                if section.dependencies:
                    print(f"     Dependencies: {', '.join(section.dependencies)}")
        
        # Display thinking log
        if result.get("plan") and result["plan"].thinking_log:
            print(f"\n💭 Thinking Log:")
            for i, thought in enumerate(result["plan"].thinking_log, 1):
                print(f"\n  {i}. {thought[:200]}...")
        
        # Display plan steps
        if result.get("plan") and result["plan"].steps:
            print(f"\n📝 Research Plan ({len(result['plan'].steps)} steps):")
            for step in result["plan"].steps[:5]:
                print(f"\n  Step {step.step_number}: {step.description}")
                if step.dependencies:
                    print(f"     Depends on: {step.dependencies}")
        
        # Check HITL status
        if result.get("awaiting_approval"):
            print("\n⏸️  HITL CHECKPOINT: Plan awaiting approval")
            print("   In a real scenario, user would review and approve/edit the plan")
            print("   For this demo, we'll simulate approval...\n")
            
            # Simulate approval
            result["awaiting_approval"] = False
            result["user_feedback"] = "Approved - proceed with research"
            
            print("✓ Plan approved, continuing to Research Manager...\n")
            
            # Run manager node
            print("▶ Running Research Manager Node...")
            result = await compiled_graph.ainvoke(result, config)
            
            print("\n✓ Research Manager completed!")
            
            # Display work packages
            if result.get("work_packages"):
                print(f"\n📦 Work Packages Created ({len(result['work_packages'])}):")
                for i, pkg in enumerate(result["work_packages"][:5], 1):
                    print(f"\n  {i}. {pkg.section_title}")
                    print(f"     Status: {pkg.status}")
                    print(f"     Queries: {', '.join(pkg.queries[:2])}")
                    if pkg.perspective:
                        print(f"     Perspective: {pkg.perspective}")
            
            # Display research wave
            if "research_wave" in result:
                print(f"\n🌊 Research Wave: {result['research_wave']}")
        
        print("\n" + "="*80)
        print("✓ DEMO COMPLETED SUCCESSFULLY")
        print("="*80 + "\n")
        
        print("Summary:")
        print(f"  - Perspectives: {len(result.get('perspectives', []))}")
        print(f"  - Outline sections: {len(result.get('plan', {}).outline) if result.get('plan') else 0}")
        print(f"  - Plan steps: {len(result.get('plan', {}).steps) if result.get('plan') else 0}")
        print(f"  - Work packages: {len(result.get('work_packages', []))}")
        print(f"  - Research wave: {result.get('research_wave', 0)}")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
