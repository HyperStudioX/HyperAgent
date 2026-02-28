"""Tests for the parallel multi-agent execution system."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.parallel import (
    DEFAULT_PARALLEL_AGENTS,
    MAX_PARALLEL_AGENTS,
    ParallelExecutionResult,
    ParallelExecutor,
    SubTask,
    _execute_sub_task,
    decompose_query,
    is_parallelizable_query,
    synthesize_results,
)


# ---------------------------------------------------------------------------
# SubTask dataclass tests
# ---------------------------------------------------------------------------


class TestSubTask:
    def test_default_values(self):
        task = SubTask()
        assert task.query == ""
        assert task.focus_area == ""
        assert task.status == "pending"
        assert task.result == ""
        assert task.error is None
        assert task.duration_ms == 0
        assert len(task.id) == 8

    def test_custom_values(self):
        task = SubTask(
            id="abc12345",
            query="What is AI?",
            focus_area="AI basics",
            status="completed",
            result="AI is...",
            error=None,
            duration_ms=500,
        )
        assert task.id == "abc12345"
        assert task.query == "What is AI?"
        assert task.focus_area == "AI basics"
        assert task.status == "completed"
        assert task.result == "AI is..."
        assert task.duration_ms == 500

    def test_unique_ids(self):
        task1 = SubTask()
        task2 = SubTask()
        assert task1.id != task2.id


# ---------------------------------------------------------------------------
# ParallelExecutionResult dataclass tests
# ---------------------------------------------------------------------------


class TestParallelExecutionResult:
    def test_default_values(self):
        result = ParallelExecutionResult(sub_tasks=[])
        assert result.sub_tasks == []
        assert result.synthesis == ""
        assert result.total_duration_ms == 0
        assert result.successful_count == 0
        assert result.failed_count == 0

    def test_with_sub_tasks(self):
        tasks = [
            SubTask(query="q1", status="completed"),
            SubTask(query="q2", status="failed"),
        ]
        result = ParallelExecutionResult(
            sub_tasks=tasks,
            synthesis="Combined findings",
            total_duration_ms=3000,
            successful_count=1,
            failed_count=1,
        )
        assert len(result.sub_tasks) == 2
        assert result.synthesis == "Combined findings"
        assert result.total_duration_ms == 3000
        assert result.successful_count == 1
        assert result.failed_count == 1


# ---------------------------------------------------------------------------
# is_parallelizable_query tests
# ---------------------------------------------------------------------------


class TestIsParallelizableQuery:
    def test_simple_question_not_parallelizable(self):
        assert is_parallelizable_query("What is Python?") is False

    def test_hello_not_parallelizable(self):
        assert is_parallelizable_query("Hello, how are you?") is False

    def test_short_question_not_parallelizable(self):
        assert is_parallelizable_query("What time is it?") is False

    def test_comprehensive_research_is_parallelizable(self):
        query = "Write a comprehensive research paper on the state of the art in AI agents"
        assert is_parallelizable_query(query) is True

    def test_detailed_analysis_is_parallelizable(self):
        query = "Provide a detailed analysis comparing different deep learning frameworks"
        assert is_parallelizable_query(query) is True

    def test_survey_review_is_parallelizable(self):
        query = "Survey and review the landscape of large language models"
        assert is_parallelizable_query(query) is True

    def test_pros_cons_with_multiple_aspects_is_parallelizable(self):
        query = "Analyze the pros and cons of various cloud computing platforms"
        assert is_parallelizable_query(query) is True

    def test_single_keyword_with_long_query_is_parallelizable(self):
        query = (
            "I want a comprehensive understanding of how machine learning is being applied "
            "across different industries and what impact it has had on productivity and costs"
        )
        assert is_parallelizable_query(query) is True

    def test_single_keyword_short_query_not_parallelizable(self):
        query = "Give me a quick overview"
        assert is_parallelizable_query(query) is False


# ---------------------------------------------------------------------------
# decompose_query tests
# ---------------------------------------------------------------------------


class TestDecomposeQuery:
    @pytest.mark.asyncio
    async def test_successful_decomposition(self):
        """Test decompose_query with mocked LLM returning valid JSON."""
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"query": "Sub-query 1 about AI agents", "focus_area": "Agent architectures"},
            {"query": "Sub-query 2 about LLM models", "focus_area": "LLM models"},
            {"query": "Sub-query 3 about evaluation", "focus_area": "Evaluation methods"},
        ])

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Comprehensive analysis of AI agents")

        assert len(result) == 3
        assert all(isinstance(t, SubTask) for t in result)
        assert result[0].query == "Sub-query 1 about AI agents"
        assert result[0].focus_area == "Agent architectures"
        assert result[1].query == "Sub-query 2 about LLM models"
        assert result[2].focus_area == "Evaluation methods"

    @pytest.mark.asyncio
    async def test_decomposition_with_markdown_code_block(self):
        """Test that markdown code blocks are stripped."""
        mock_response = MagicMock()
        mock_response.content = '```json\n[{"query": "Test query", "focus_area": "Test"}]\n```'

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Some query")

        assert len(result) == 1
        assert result[0].query == "Test query"

    @pytest.mark.asyncio
    async def test_decomposition_respects_max_tasks(self):
        """Test that max_tasks limits the number of sub-tasks."""
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"query": f"Query {i}", "focus_area": f"Area {i}"}
            for i in range(10)
        ])

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Big query", max_tasks=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_decomposition_fallback_on_llm_failure(self):
        """Test that LLM failure returns the original query as a single task."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("My research query")

        assert len(result) == 1
        assert result[0].query == "My research query"
        assert result[0].focus_area == "Full research"

    @pytest.mark.asyncio
    async def test_decomposition_fallback_on_invalid_json(self):
        """Test that invalid JSON from LLM triggers fallback."""
        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Some query")

        assert len(result) == 1
        assert result[0].query == "Some query"
        assert result[0].focus_area == "Full research"

    @pytest.mark.asyncio
    async def test_decomposition_skips_invalid_items(self):
        """Test that items without 'query' key are skipped."""
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"query": "Valid query", "focus_area": "Valid"},
            {"bad_key": "No query here"},
            "just a string",
        ])

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Some query")

        assert len(result) == 1
        assert result[0].query == "Valid query"

    @pytest.mark.asyncio
    async def test_decomposition_default_focus_area(self):
        """Test that missing focus_area defaults to 'General'."""
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"query": "Query without focus area"},
        ])

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await decompose_query("Some query")

        assert result[0].focus_area == "General"


# ---------------------------------------------------------------------------
# synthesize_results tests
# ---------------------------------------------------------------------------


class TestSynthesizeResults:
    @pytest.mark.asyncio
    async def test_successful_synthesis(self):
        """Test synthesis with mocked LLM."""
        sub_tasks = [
            SubTask(query="Q1", focus_area="Area 1", status="completed", result="Finding 1"),
            SubTask(query="Q2", focus_area="Area 2", status="completed", result="Finding 2"),
        ]

        mock_response = MagicMock()
        mock_response.content = "Comprehensive synthesis of findings 1 and 2."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await synthesize_results("Original query", sub_tasks)

        assert result == "Comprehensive synthesis of findings 1 and 2."

    @pytest.mark.asyncio
    async def test_synthesis_with_no_successful_tasks(self):
        """Test synthesis when all tasks failed."""
        sub_tasks = [
            SubTask(query="Q1", status="failed", error="Error"),
            SubTask(query="Q2", status="failed", error="Error"),
        ]

        result = await synthesize_results("Original query", sub_tasks)

        assert "all sub-queries failed" in result.lower()

    @pytest.mark.asyncio
    async def test_synthesis_excludes_failed_tasks(self):
        """Test that failed tasks are not included in synthesis."""
        sub_tasks = [
            SubTask(query="Q1", focus_area="Area 1", status="completed", result="Finding 1"),
            SubTask(query="Q2", focus_area="Area 2", status="failed", result=""),
        ]

        mock_response = MagicMock()
        mock_response.content = "Synthesis with only finding 1."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await synthesize_results("Original query", sub_tasks)

        assert result == "Synthesis with only finding 1."
        # Verify the LLM was called (only 1 successful task)
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Area 1" in call_args[0].content
        assert "Area 2" not in call_args[0].content

    @pytest.mark.asyncio
    async def test_synthesis_fallback_on_llm_failure(self):
        """Test that LLM failure produces a concatenated fallback."""
        sub_tasks = [
            SubTask(query="Q1", focus_area="Area 1", status="completed", result="Finding 1"),
        ]

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch("app.agents.parallel.llm_service") as mock_svc:
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await synthesize_results("Original query", sub_tasks)

        assert "synthesis unavailable" in result.lower()
        assert "Finding 1" in result


# ---------------------------------------------------------------------------
# _execute_sub_task tests
# ---------------------------------------------------------------------------


class TestExecuteSubTask:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful sub-task execution with mocked web_search and LLM."""
        sub_task = SubTask(query="What is AI?", focus_area="AI basics")

        mock_search_tool = MagicMock()
        mock_search_tool.ainvoke = AsyncMock(return_value="Search result about AI")

        mock_llm_response = MagicMock()
        mock_llm_response.content = "AI is artificial intelligence."
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        with (
            patch("app.agents.parallel.llm_service") as mock_svc,
            patch("app.agents.tools.web_search.web_search", mock_search_tool),
        ):
            mock_svc.get_llm_for_tier.return_value = mock_llm

            result = await _execute_sub_task(sub_task)

        assert result.status == "completed"
        assert result.result == "AI is artificial intelligence."
        assert result.duration_ms > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """Test sub-task failure when web_search raises an error."""
        sub_task = SubTask(query="What is AI?", focus_area="AI basics")

        mock_search_tool = MagicMock()
        mock_search_tool.ainvoke = AsyncMock(side_effect=RuntimeError("Search failed"))

        with patch("app.agents.tools.web_search.web_search", mock_search_tool):
            result = await _execute_sub_task(sub_task)

        assert result.status == "failed"
        assert result.error is not None
        assert "Search failed" in result.error
        assert result.duration_ms > 0


# ---------------------------------------------------------------------------
# ParallelExecutor tests
# ---------------------------------------------------------------------------


class TestParallelExecutor:
    def test_max_agents_cap(self):
        """Test that max_agents is capped at MAX_PARALLEL_AGENTS."""
        executor = ParallelExecutor(max_agents=100)
        assert executor.max_agents == MAX_PARALLEL_AGENTS

    def test_default_max_agents(self):
        """Test default max_agents value."""
        executor = ParallelExecutor()
        assert executor.max_agents == DEFAULT_PARALLEL_AGENTS

    def test_custom_max_agents(self):
        """Test custom max_agents within limits."""
        executor = ParallelExecutor(max_agents=3)
        assert executor.max_agents == 3

    @pytest.mark.asyncio
    async def test_execute_end_to_end(self):
        """Test full execute pipeline with mocked dependencies."""
        # Mock decompose_query
        mock_sub_tasks = [
            SubTask(id="t1", query="Sub Q1", focus_area="Area 1"),
            SubTask(id="t2", query="Sub Q2", focus_area="Area 2"),
        ]

        # Track progress events
        progress_events = []

        with (
            patch("app.agents.parallel.decompose_query", new_callable=AsyncMock) as mock_decompose,
            patch("app.agents.parallel._execute_sub_task", new_callable=AsyncMock) as mock_exec,
            patch("app.agents.parallel.synthesize_results", new_callable=AsyncMock) as mock_synth,
        ):
            mock_decompose.return_value = mock_sub_tasks

            # _execute_sub_task modifies the SubTask in place and returns it
            async def side_effect_exec(sub_task, provider=None):
                sub_task.status = "completed"
                sub_task.result = f"Result for {sub_task.query}"
                sub_task.duration_ms = 100
                return sub_task

            mock_exec.side_effect = side_effect_exec
            mock_synth.return_value = "Final synthesis"

            executor = ParallelExecutor(max_agents=5)
            result = await executor.execute(
                query="Comprehensive AI analysis",
                provider="anthropic",
                on_progress=lambda e: progress_events.append(e),
            )

        assert isinstance(result, ParallelExecutionResult)
        assert result.synthesis == "Final synthesis"
        assert result.successful_count == 2
        assert result.failed_count == 0
        assert result.total_duration_ms > 0
        assert len(result.sub_tasks) == 2

        # Verify progress events were emitted
        assert len(progress_events) > 0

        # Check for decompose, execute, synthesize stages
        stage_events = [e for e in progress_events if e.get("type") == "stage"]
        stage_names = [e.get("name") for e in stage_events]
        assert "parallel_decompose" in stage_names
        assert "parallel_execute" in stage_names
        assert "parallel_synthesize" in stage_names

        # Check for parallel_task events
        task_events = [e for e in progress_events if e.get("type") == "parallel_task"]
        assert len(task_events) >= 2  # At least pending + completed for each task

    @pytest.mark.asyncio
    async def test_execute_with_failures(self):
        """Test execute when some sub-tasks fail via gather exceptions."""
        mock_sub_tasks = [
            SubTask(id="t1", query="Sub Q1", focus_area="Area 1"),
            SubTask(id="t2", query="Sub Q2", focus_area="Area 2"),
        ]

        call_count = 0

        with (
            patch("app.agents.parallel.decompose_query", new_callable=AsyncMock) as mock_decompose,
            patch("app.agents.parallel._execute_sub_task", new_callable=AsyncMock) as mock_exec,
            patch("app.agents.parallel.synthesize_results", new_callable=AsyncMock) as mock_synth,
        ):
            mock_decompose.return_value = mock_sub_tasks

            async def side_effect_exec(sub_task, provider=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    sub_task.status = "completed"
                    sub_task.result = "Success"
                    sub_task.duration_ms = 50
                    return sub_task
                else:
                    raise RuntimeError("Sub-task failed")

            mock_exec.side_effect = side_effect_exec
            mock_synth.return_value = "Partial synthesis"

            executor = ParallelExecutor(max_agents=5)
            result = await executor.execute(query="Test query")

        assert result.successful_count == 1
        assert result.failed_count == 1
        assert result.synthesis == "Partial synthesis"

    @pytest.mark.asyncio
    async def test_execute_without_progress_callback(self):
        """Test execute works without on_progress callback."""
        mock_sub_tasks = [
            SubTask(id="t1", query="Sub Q1", focus_area="Area 1"),
        ]

        with (
            patch("app.agents.parallel.decompose_query", new_callable=AsyncMock) as mock_decompose,
            patch("app.agents.parallel._execute_sub_task", new_callable=AsyncMock) as mock_exec,
            patch("app.agents.parallel.synthesize_results", new_callable=AsyncMock) as mock_synth,
        ):
            mock_decompose.return_value = mock_sub_tasks

            async def side_effect_exec(sub_task, provider=None):
                sub_task.status = "completed"
                sub_task.result = "Done"
                sub_task.duration_ms = 10
                return sub_task

            mock_exec.side_effect = side_effect_exec
            mock_synth.return_value = "Synthesis"

            executor = ParallelExecutor(max_agents=5)
            # Should not raise even without on_progress
            result = await executor.execute(query="Test query")

        assert result.synthesis == "Synthesis"


# ---------------------------------------------------------------------------
# Events integration tests
# ---------------------------------------------------------------------------


class TestParallelTaskEvent:
    def test_event_type_exists(self):
        """Test that PARALLEL_TASK event type is registered."""
        from app.agents.events import EventType
        assert EventType.PARALLEL_TASK == "parallel_task"

    def test_parallel_task_factory(self):
        """Test the parallel_task factory function."""
        from app.agents.events import parallel_task

        event = parallel_task(
            task_id="t1",
            focus_area="AI basics",
            status="running",
            query="What is AI?",
            duration_ms=500,
        )

        assert event["type"] == "parallel_task"
        assert event["task_id"] == "t1"
        assert event["focus_area"] == "AI basics"
        assert event["status"] == "running"
        assert event["query"] == "What is AI?"
        assert event["duration_ms"] == 500
        assert "timestamp" in event

    def test_parallel_task_factory_minimal(self):
        """Test the parallel_task factory with only required fields."""
        from app.agents.events import parallel_task

        event = parallel_task(
            task_id="t2",
            focus_area="General",
            status="pending",
        )

        assert event["type"] == "parallel_task"
        assert event["task_id"] == "t2"
        assert event["query"] is None
        assert event["duration_ms"] is None
