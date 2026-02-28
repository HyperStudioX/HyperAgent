"""Routing accuracy evaluation tests."""

import pytest

from evals.evaluators.routing_evaluator import RoutingEvaluator


class TestRoutingAccuracy:
    """Test suite for routing accuracy evaluation."""

    @pytest.mark.asyncio
    async def test_routing_accuracy_with_mock(self, routing_cases, mock_supervisor):
        """Test routing accuracy using mock supervisor.

        Args:
            routing_cases: Test cases from routing.json
            mock_supervisor: Mock supervisor fixture
        """
        results = []

        for case in routing_cases:
            result = await mock_supervisor.route(case["input"])
            passed = result["next_agent"].lower() == case["expected_agent"].lower()
            results.append(
                {
                    "id": case["id"],
                    "input": case["input"],
                    "expected_agent": case["expected_agent"],
                    "actual_agent": result["next_agent"],
                    "passed": passed,
                    "category": case.get("category", "unknown"),
                }
            )

        # Calculate accuracy
        accuracy = sum(r["passed"] for r in results) / len(results)

        # Print detailed results for debugging
        passed_count = sum(r["passed"] for r in results)
        print(f"\n{'=' * 60}")
        print(f"Routing Accuracy: {accuracy:.1%} ({passed_count}/{len(results)})")
        print(f"{'=' * 60}")

        # Show failures
        failures = [r for r in results if not r["passed"]]
        if failures:
            print("\nFailures:")
            for f in failures:
                print(f"  - {f['id']}: expected '{f['expected_agent']}', got '{f['actual_agent']}'")
                print(f"    Input: {f['input'][:60]}...")

        # Assert minimum accuracy threshold
        assert accuracy >= 0.9, f"Routing accuracy {accuracy:.1%} < 90% threshold"

    @pytest.mark.asyncio
    async def test_routing_by_category(self, routing_cases, mock_supervisor):
        """Test routing accuracy broken down by category.

        Args:
            routing_cases: Test cases from routing.json
            mock_supervisor: Mock supervisor fixture
        """
        category_results: dict[str, list[bool]] = {}

        for case in routing_cases:
            result = await mock_supervisor.route(case["input"])
            passed = result["next_agent"].lower() == case["expected_agent"].lower()

            category = case.get("category", "unknown")
            if category not in category_results:
                category_results[category] = []
            category_results[category].append(passed)

        print(f"\n{'=' * 60}")
        print("Routing Accuracy by Category:")
        print(f"{'=' * 60}")

        for category, results in sorted(category_results.items()):
            accuracy = sum(results) / len(results)
            print(f"  {category}: {accuracy:.1%} ({sum(results)}/{len(results)})")

            # Each category should have at least 80% accuracy
            assert accuracy >= 0.8, f"Category '{category}' accuracy {accuracy:.1%} < 80%"

    def test_routing_evaluator_correct(self):
        """Test RoutingEvaluator with correct routing."""
        evaluator = RoutingEvaluator()
        result = evaluator.evaluate(
            expected_agent="task",
            actual_agent="task",
            query="Hello world",
        )

        assert result.score == 1.0
        assert result.metadata["correct"] is True

    def test_routing_evaluator_incorrect(self):
        """Test RoutingEvaluator with incorrect routing."""
        evaluator = RoutingEvaluator()
        result = evaluator.evaluate(
            expected_agent="research",
            actual_agent="task",
            query="Write a comprehensive research paper",
        )

        assert result.score == 0.0
        assert result.metadata["correct"] is False

    def test_routing_evaluator_case_insensitive(self):
        """Test RoutingEvaluator is case-insensitive."""
        evaluator = RoutingEvaluator()
        result = evaluator.evaluate(
            expected_agent="TASK",
            actual_agent="task",
            query="Hello",
        )

        assert result.score == 1.0

    def test_routing_evaluator_batch(self, routing_cases):
        """Test batch evaluation functionality."""
        evaluator = RoutingEvaluator()

        # Create mock results
        mock_results = [
            {
                "expected_agent": case["expected_agent"],
                "actual_agent": case["expected_agent"],  # All correct
                "query": case["input"],
                "category": case.get("category", "unknown"),
            }
            for case in routing_cases[:5]
        ]

        summary = evaluator.evaluate_batch(mock_results)

        assert summary["accuracy"] == 1.0
        assert summary["correct"] == 5
        assert summary["total"] == 5


class TestRoutingEdgeCases:
    """Test edge cases for routing."""

    @pytest.mark.asyncio
    async def test_empty_query(self, mock_supervisor):
        """Empty query should default to task."""
        result = await mock_supervisor.route("")
        assert result["next_agent"] == "task"

    @pytest.mark.asyncio
    async def test_ambiguous_query(self, mock_supervisor):
        """Ambiguous query should route to task as default."""
        result = await mock_supervisor.route("help")
        assert result["next_agent"] == "task"

    @pytest.mark.asyncio
    async def test_mixed_signals_query(self, mock_supervisor):
        """Query with mixed signals should pick the dominant one."""
        # This query mentions research but is really about task
        result = await mock_supervisor.route("Can you quickly search for information about AI?")
        assert result["next_agent"] == "task"


class TestRoutingSpecificAgents:
    """Test routing to specific agents."""

    @pytest.mark.asyncio
    async def test_research_agent_routing(self, mock_supervisor):
        """Test queries that should route to research agent."""
        research_queries = [
            "Write a comprehensive 20-page research paper on quantum computing with citations",
            "Create an academic literature review with 30+ citations from peer-reviewed sources",
            "Conduct comprehensive market analysis with competitor research",
        ]

        for query in research_queries:
            result = await mock_supervisor.route(query)
            msg = f"Query should route to research: {query[:50]}..."
            assert result["next_agent"] == "research", msg

    @pytest.mark.asyncio
    async def test_data_queries_route_to_task(self, mock_supervisor):
        """Test queries about data analysis route to task agent (has data_analysis skill)."""
        data_queries = [
            "Analyze this CSV file and create visualizations",
            "Process this Excel spreadsheet and find trends",
            "Run statistical analysis on this dataset",
        ]

        for query in data_queries:
            result = await mock_supervisor.route(query)
            assert result["next_agent"] == "task", f"Query should route to task: {query[:50]}..."

    @pytest.mark.asyncio
    async def test_task_agent_routing(self, mock_supervisor):
        """Test queries that should route to task agent."""
        task_queries = [
            "Hello, how are you?",
            "Generate an image of a sunset",
            "Write a Python function for sorting",
            "What's the weather today?",
        ]

        for query in task_queries:
            result = await mock_supervisor.route(query)
            assert result["next_agent"] == "task", f"Query should route to task: {query[:50]}..."
