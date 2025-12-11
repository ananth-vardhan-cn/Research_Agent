"""Tests for Writer, Reviewer, and Publisher nodes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from research_agent.models.state import (
    ResearchState, Task, Plan, Section, ResearchData, DraftSection, Critique, FinalReport, Source
)
from research_agent.nodes.writer import writer_node
from research_agent.nodes.reviewer import reviewer_node
from research_agent.nodes.publisher import publisher_node
from research_agent.llm.gemini import GeminiClient

@pytest.fixture
def mock_gemini_client():
    client = MagicMock(spec=GeminiClient)
    client.generate = AsyncMock(return_value="# Draft Content\n\nThis is a draft section with a citation [source_1].")
    client.generate_structured = AsyncMock(return_value={
        "issues": ["Issue 1"],
        "suggestions": ["Suggestion 1"],
        "severity": "low"
    })
    return client

@pytest.fixture
def basic_state():
    return ResearchState(
        task=Task(query="Test Query"),
        plan=Plan(
            title="Test Plan",
            outline=[
                Section(
                    title="Section 1", 
                    description="Desc 1", 
                    subsections=["Sub 1"],
                    dependencies=[],
                    required_sources=[],
                    perspectives=[]
                )
            ],
            steps=[],
            perspectives=[],
            thinking_log=[]
        ),
        research_data=[
            ResearchData(
                source_id="source_1",
                content="Relevant content",
                metadata={"url": "http://example.com"},
                collected_at=datetime.now()
            )
        ],
        source_map={"source_1": Source(url="http://example.com", title="Example", snippet="snippet")}
    )

@pytest.mark.asyncio
async def test_writer_node(mock_gemini_client, basic_state):
    # Test generation
    new_state = await writer_node(basic_state, mock_gemini_client)
    
    assert "draft_sections" in new_state
    assert len(new_state["draft_sections"]) == 1
    assert new_state["draft_sections"][0].title == "Section 1"
    assert new_state["draft_sections"][0].content == "# Draft Content\n\nThis is a draft section with a citation [source_1]."
    assert "source_1" in new_state["draft_sections"][0].sources

@pytest.mark.asyncio
async def test_writer_node_with_critique(mock_gemini_client, basic_state):
    # Test revision
    basic_state["revision_count"] = 1
    basic_state["critique"] = Critique(issues=["Fix this"], suggestions=["Do that"], severity="medium")
    
    mock_gemini_client.generate = AsyncMock(return_value="# Revised Content\n\nRevised content.")
    
    new_state = await writer_node(basic_state, mock_gemini_client)
    
    assert "draft_sections" in new_state
    # Check that critique was cleared
    assert new_state["critique"] is None
    
    # Verify prompt included critique (simplified check)
    call_args = mock_gemini_client.generate.call_args[1]
    assert "CRITIQUE TO ADDRESS" in call_args["prompt"]

@pytest.mark.asyncio
async def test_reviewer_node(mock_gemini_client, basic_state):
    basic_state["draft_sections"] = [
        DraftSection(title="S1", content="Content [source_1]", sources=["source_1"], order=0)
    ]
    
    new_state = await reviewer_node(basic_state, mock_gemini_client)
    
    assert "critique" in new_state
    assert "revision_count" in new_state
    assert new_state["revision_count"] == 1
    assert new_state["critique"].severity == "low"

@pytest.mark.asyncio
async def test_reviewer_node_validation_error(mock_gemini_client, basic_state):
    # Missing source in map
    basic_state["draft_sections"] = [
        DraftSection(title="S1", content="Content [source_missing]", sources=["source_missing"], order=0)
    ]
    
    mock_gemini_client.generate_structured.return_value = {"issues": [], "suggestions": [], "severity": "low"}
    
    new_state = await reviewer_node(basic_state, mock_gemini_client)
    
    critique = new_state["critique"]
    # Should detect missing source and upgrade severity
    assert any("Missing source definition" in i for i in critique.issues)
    assert critique.severity == "medium"

@pytest.mark.asyncio
async def test_publisher_node(mock_gemini_client, basic_state):
    basic_state["draft_sections"] = [
        DraftSection(title="S1", content="Content", sources=[], order=0)
    ]
    
    new_state = await publisher_node(basic_state, mock_gemini_client)
    
    assert "final_report" in new_state
    # Expect 1 draft section + 1 references section
    assert len(new_state["final_report"].sections) == 2 
    assert new_state["final_report"].sections[1].title == "References"
    # Check for title/url instead of ID since it's formatted
    assert "Example" in new_state["final_report"].sections[1].content
    assert "http://example.com" in new_state["final_report"].sections[1].content
    assert len(new_state["final_report"].references) == 1 # source_1 from basic_state
    assert new_state["user_feedback"] is None
