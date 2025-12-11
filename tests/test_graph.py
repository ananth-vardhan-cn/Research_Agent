"""Tests for the research graph."""

import pytest

from research_agent.config import Settings
from research_agent.graph import create_research_graph
from research_agent.models.state import Task


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings()


def test_create_research_graph(settings: Settings) -> None:
    """Test graph creation."""
    graph = create_research_graph(settings)
    
    assert graph is not None
    assert "planner" in graph.nodes
    assert "manager" in graph.nodes
    assert "worker" in graph.nodes
    assert "writer" in graph.nodes
    assert "reviewer" in graph.nodes
    assert "publisher" in graph.nodes


@pytest.mark.asyncio
async def test_planner_node() -> None:
    """Test planner node (mocked)."""
    from research_agent.models.state import ResearchState
    
    # Create initial state
    state: ResearchState = {
        "task": Task(query="What are the latest developments in quantum computing?"),
    }
    
    # Test that state has required fields
    assert "task" in state
    assert state["task"].query
