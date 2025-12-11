"""Tests for reducer concurrency semantics."""

import pytest

from research_agent.models.state import ResearchData, research_data_reducer


def test_reducer_with_empty_existing() -> None:
    """Test reducer with no existing data."""
    new_data = [
        ResearchData(source_id="src_1", content="Content 1"),
        ResearchData(source_id="src_2", content="Content 2"),
    ]
    
    result = research_data_reducer(None, new_data)
    
    assert len(result) == 2
    assert result[0].source_id == "src_1"
    assert result[1].source_id == "src_2"


def test_reducer_merges_unique_entries() -> None:
    """Test reducer merges unique entries from parallel workers."""
    # Simulate worker 1 results
    existing = [
        ResearchData(source_id="worker1_src1", content="Worker 1 content 1"),
        ResearchData(source_id="worker1_src2", content="Worker 1 content 2"),
    ]
    
    # Simulate worker 2 results
    new_data = [
        ResearchData(source_id="worker2_src1", content="Worker 2 content 1"),
        ResearchData(source_id="worker2_src2", content="Worker 2 content 2"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    # Should have all 4 unique entries
    assert len(result) == 4
    
    source_ids = {item.source_id for item in result}
    assert source_ids == {"worker1_src1", "worker1_src2", "worker2_src1", "worker2_src2"}


def test_reducer_deduplicates_by_source_id() -> None:
    """Test reducer deduplicates entries with same source_id."""
    # Worker 1 finds a source
    existing = [
        ResearchData(source_id="duplicate_src", content="Old content"),
    ]
    
    # Worker 2 finds the same source (or it's an update)
    new_data = [
        ResearchData(source_id="duplicate_src", content="New content"),
        ResearchData(source_id="unique_src", content="Unique content"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    # Should have 2 entries (deduplicated)
    assert len(result) == 2
    
    # The duplicate should have the newer content
    duplicate = next(item for item in result if item.source_id == "duplicate_src")
    assert duplicate.content == "New content"


def test_reducer_multiple_merges() -> None:
    """Test reducer with multiple sequential merges simulating parallel workers."""
    # Initial state
    state: list[ResearchData] = []
    
    # Worker 1 completes
    worker1_data = [
        ResearchData(source_id="w1_s1", content="Worker 1 Source 1"),
        ResearchData(source_id="w1_s2", content="Worker 1 Source 2"),
    ]
    state = research_data_reducer(state if state else None, worker1_data)
    
    assert len(state) == 2
    
    # Worker 2 completes
    worker2_data = [
        ResearchData(source_id="w2_s1", content="Worker 2 Source 1"),
        ResearchData(source_id="w2_s2", content="Worker 2 Source 2"),
    ]
    state = research_data_reducer(state, worker2_data)
    
    assert len(state) == 4
    
    # Worker 3 completes with some duplicates
    worker3_data = [
        ResearchData(source_id="w1_s1", content="Worker 3 updated Source 1"),
        ResearchData(source_id="w3_s1", content="Worker 3 Source 1"),
    ]
    state = research_data_reducer(state, worker3_data)
    
    # Should have 5 unique entries (w1_s1, w1_s2, w2_s1, w2_s2, w3_s1)
    assert len(state) == 5
    
    # Check that w1_s1 was updated
    w1_s1 = next(item for item in state if item.source_id == "w1_s1")
    assert "Worker 3" in w1_s1.content


def test_reducer_preserves_order() -> None:
    """Test reducer maintains chronological order by collected_at."""
    import time
    
    # Create data with slight time differences
    existing = [
        ResearchData(source_id="src_1", content="Content 1"),
    ]
    
    # Small delay to ensure different timestamps
    time.sleep(0.01)
    
    new_data = [
        ResearchData(source_id="src_2", content="Content 2"),
        ResearchData(source_id="src_3", content="Content 3"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    # Should be ordered by collected_at
    assert len(result) == 3
    for i in range(len(result) - 1):
        assert result[i].collected_at <= result[i + 1].collected_at


def test_reducer_handles_empty_new_data() -> None:
    """Test reducer handles empty new data."""
    existing = [
        ResearchData(source_id="src_1", content="Content 1"),
    ]
    
    result = research_data_reducer(existing, [])
    
    assert len(result) == 1
    assert result[0].source_id == "src_1"


def test_reducer_deterministic_merge() -> None:
    """Test reducer produces deterministic results regardless of merge order."""
    # Create same data in different orders
    data_a = ResearchData(source_id="src_a", content="Content A")
    data_b = ResearchData(source_id="src_b", content="Content B")
    data_c = ResearchData(source_id="src_c", content="Content C")
    
    # Merge order 1: (A, B) then C
    result1 = research_data_reducer(None, [data_a, data_b])
    result1 = research_data_reducer(result1, [data_c])
    
    # Merge order 2: (A, C) then B
    result2 = research_data_reducer(None, [data_a, data_c])
    result2 = research_data_reducer(result2, [data_b])
    
    # Both should have same source_ids (order might differ due to timestamps)
    ids1 = {item.source_id for item in result1}
    ids2 = {item.source_id for item in result2}
    
    assert ids1 == ids2
    assert len(result1) == 3
    assert len(result2) == 3


def test_reducer_parallel_worker_simulation() -> None:
    """Test realistic parallel worker scenario."""
    # Initial empty state
    state: list[ResearchData] = []
    
    # Simulate 5 parallel workers completing at different times
    workers = [
        [ResearchData(source_id=f"worker1_src{i}", content=f"Worker 1 content {i}") 
         for i in range(3)],
        [ResearchData(source_id=f"worker2_src{i}", content=f"Worker 2 content {i}") 
         for i in range(2)],
        [ResearchData(source_id=f"worker3_src{i}", content=f"Worker 3 content {i}") 
         for i in range(4)],
        [ResearchData(source_id="worker1_src0", content="Worker 4 updated content"),
         ResearchData(source_id=f"worker4_src0", content="Worker 4 content 0")],
        [ResearchData(source_id=f"worker5_src{i}", content=f"Worker 5 content {i}") 
         for i in range(2)],
    ]
    
    # Apply each worker's results
    for worker_data in workers:
        state = research_data_reducer(state if state else None, worker_data)
    
    # Count unique sources
    source_ids = {item.source_id for item in state}
    
    # Should have: 3 from w1 + 2 from w2 + 4 from w3 + 2 from w4 + 2 from w5
    # Minus 1 duplicate (worker1_src0 updated by w4) = 12 unique
    assert len(source_ids) == 12
    
    # Verify the duplicate was updated
    worker1_src0 = next(item for item in state if item.source_id == "worker1_src0")
    assert "Worker 4" in worker1_src0.content


def test_reducer_with_metadata() -> None:
    """Test reducer preserves metadata in research data."""
    existing = [
        ResearchData(
            source_id="src_1",
            content="Content 1",
            metadata={"quality": "high", "verified": True},
        ),
    ]
    
    new_data = [
        ResearchData(
            source_id="src_2",
            content="Content 2",
            metadata={"quality": "medium", "verified": False},
        ),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    assert len(result) == 2
    assert result[0].metadata.get("quality") is not None
    assert result[1].metadata.get("quality") is not None


def test_reducer_with_perspectives() -> None:
    """Test reducer handles research data with different perspectives."""
    existing = [
        ResearchData(source_id="src_1", content="Content 1", perspective="Technical"),
    ]
    
    new_data = [
        ResearchData(source_id="src_2", content="Content 2", perspective="Business"),
        ResearchData(source_id="src_3", content="Content 3", perspective="Academic"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    assert len(result) == 3
    perspectives = {item.perspective for item in result if item.perspective}
    assert perspectives == {"Technical", "Business", "Academic"}
