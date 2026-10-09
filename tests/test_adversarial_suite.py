import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.synthesis.strategy_generator import extract_relevant_snippets, DualLayerContextEngine
from src.config import Tier
import src.jobs.forager_job
import src.delivery.telegram_bot

class TestAdversarialSnippetExtraction(unittest.TestCase):
    """Rigorous boundary and stress tests for extract_relevant_snippets"""

    def test_null_and_empty_inputs(self):
        self.assertEqual(extract_relevant_snippets("", "query"), [])
        self.assertEqual(extract_relevant_snippets(None, "query"), [])
        self.assertEqual(extract_relevant_snippets("some text", ""), [])
        self.assertEqual(extract_relevant_snippets("some text", None), [])
        self.assertEqual(extract_relevant_snippets("", ""), [])
        self.assertEqual(extract_relevant_snippets(None, None), [])

    def test_single_word_and_short_texts(self):
        self.assertEqual(extract_relevant_snippets("word", "word"), ["word"])
        self.assertEqual(extract_relevant_snippets("hello world", "world"), ["hello world"])
        self.assertEqual(extract_relevant_snippets("hello world", "unmatched"), ["hello world"])

    def test_query_with_no_valid_terms(self):
        # Query with only 1 or 2 letter words (below 3 char regex threshold)
        text = "This is a longer text that contains more than 10 words to verify fallback behavior."
        res = extract_relevant_snippets(text, "is a to")
        self.assertTrue(len(res) > 0)
        self.assertIn("This is a longer", res[0])

    def test_special_characters_and_unicode(self):
        special_text = (
            "🚀 High-frequency distributed systems utilize Raft consensus algorithms! "
            "Edge cases: <script>alert('xss')</script> & {key: 'value'} [item1, item2] "
            "Mathematical notation: ∀x ∈ S, ∃y | f(x) = y. "
            "Punctuation: !@#$%^&*()_+=-`~?><,./|\\."
        )
        res = extract_relevant_snippets(special_text, "Raft consensus algorithms", window_size=50)
        self.assertTrue(len(res) > 0)
        self.assertIn("Raft", res[0])

        # Query with regex characters that could crash re if not sanitized
        regex_query = ".*+?^${}()|[]\\ Raft"
        res_regex = extract_relevant_snippets(special_text, regex_query, window_size=50)
        self.assertTrue(len(res_regex) > 0)

    def test_overlapping_window_suppression_and_ranking(self):
        # Construct text with target keywords placed at specific intervals
        words = ["filler"] * 1000
        # Put high relevance keyword at index 300
        words[300:305] = ["keyword", "keyword", "keyword", "keyword", "keyword"]
        # Put medium relevance keyword at index 700
        words[700:703] = ["keyword", "keyword", "keyword"]
        # Put another close to index 300 (e.g. index 320) which should be suppressed by window_size//2
        words[320:325] = ["keyword", "keyword", "keyword", "keyword", "keyword"]

        full_text = " ".join(words)
        res = extract_relevant_snippets(full_text, "keyword", window_size=100, overlap=25, top_k=2)
        self.assertEqual(len(res), 2)
        # Verify the top snippet contains keywords
        self.assertIn("keyword", res[0])
        self.assertIn("keyword", res[1])

    def test_massive_text_performance(self):
        # 50,000 words
        large_text = " ".join(["distributed database sharding replication" if i % 200 == 0 else f"token_{i}" for i in range(50000)])
        import time
        t0 = time.perf_counter()
        res = extract_relevant_snippets(large_text, "distributed database sharding", window_size=200, overlap=50, top_k=3)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 2.0, f"Snippet extraction on 50k words took {elapsed:.2f}s, expected < 2s")
        self.assertEqual(len(res), 3)
        for s in res:
            self.assertTrue(any(k in s for k in ["distributed", "database", "sharding"]))


class TestAdversarialStrategyGenerator(unittest.IsolatedAsyncioTestCase):
    """Adversarial tests for ask_brick, run_librarian, and spar_kata"""

    async def asyncSetUp(self):
        self.engine = DualLayerContextEngine()

    @patch("src.synthesis.strategy_generator.generate_completion_async", new_callable=AsyncMock)
    async def test_ask_brick_dynamic_snippet_rag(self, mock_llm):
        mock_llm.return_value = "Strategic advice on scaling."

        mock_db = AsyncMock()
        mock_brick = MagicMock()
        mock_brick.source_content_id = 42
        mock_brick.core_thesis = "Microservices architecture requires distributed tracing."

        mock_item = MagicMock()
        mock_item.id = 42
        mock_item.title = "High Scale Systems"
        mock_item.source_url = "https://example.com/scaling"
        mock_item.author = "Martin Fowler"
        mock_item.source_type = "article"
        mock_item.raw_text = " ".join(["architecture tracing observability latency telemetry" if i == 50 else "word" for i in range(500)])

        with patch.object(self.engine, "find_brick_and_source", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = (mock_brick, mock_item)

            result = await self.engine.ask_brick(
                brick_text="Core Thesis: Microservices architecture requires distributed tracing.",
                question="How does telemetry reduce latency?",
                db=mock_db,
                focus_state="Accelerate backend throughput"
            )

            self.assertEqual(result, "Strategic advice on scaling.")
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            # Verify PRO tier was requested
            self.assertEqual(call_args[0][0], Tier.PRO.value)
            messages = call_args[1]["messages"]
            prompt_content = messages[1]["content"]
            self.assertIn("TOP RELEVANT TRANSCRIPT PASSAGES", prompt_content)
            self.assertIn("telemetry", prompt_content)

    @patch("src.synthesis.strategy_generator.generate_completion_async", new_callable=AsyncMock)
    async def test_ask_brick_db_exception_resilience(self, mock_llm):
        mock_llm.return_value = "Fallback advice without crash."
        mock_db = AsyncMock()

        with patch.object(self.engine, "find_brick_and_source", side_effect=Exception("Database connection timeout")):
            result = await self.engine.ask_brick(
                brick_text="Core Thesis: Some thesis",
                question="What is the bottleneck?",
                db=mock_db
            )
            self.assertEqual(result, "Fallback advice without crash.")
            mock_llm.assert_called_once()
            # Verify it proceeded gracefully without transcript snippets
            call_args = mock_llm.call_args
            self.assertEqual(call_args[0][0], Tier.PRO.value)

    @patch("src.synthesis.strategy_generator.generate_completion_async", new_callable=AsyncMock)
    @patch("src.ingestion.embedder.get_embedder")
    async def test_run_librarian_triangulated_retrieval(self, mock_get_embedder, mock_llm):
        mock_llm.return_value = "Triangulated strategic verdict."

        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 768)
        mock_get_embedder.return_value = mock_embedder

        mock_db = AsyncMock()
        # Mock vault results
        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item1.title = "Internal Architecture Doc"
        mock_item1.source_url = "https://internal.vault/doc1"
        mock_item1.raw_text = "Internal notes on cache invalidation and redis cluster."

        mock_brick1 = MagicMock()
        mock_brick1.core_thesis = "Cache invalidation must use event-driven pub/sub."
        mock_brick1.key_mechanics = "Redis streams + CDC"
        mock_brick1.critical_pointers = ["Pointers: use consumer groups"]

        # Configure DB execution returns
        exec_results = [
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_item1])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_brick1))
        ]
        mock_db.execute = AsyncMock(side_effect=exec_results)

        # Mock DDGS live search
        mock_ddg_results = [
            {"title": "Redis 7.2 Release", "href": "https://redis.io/news", "body": "Redis 7.2 introduces cluster sharding improvements."}
        ]
        with patch("duckduckgo_search.DDGS.text", return_value=mock_ddg_results):
            result = await self.engine.run_librarian(
                query="How to scale redis clustering?",
                db=mock_db,
                focus_state="Cluster reliability"
            )

            self.assertEqual(result, "Triangulated strategic verdict.")
            mock_llm.assert_called_once()
            messages = mock_llm.call_args[1]["messages"]
            user_msg = messages[1]["content"]

            # Assert both Private Vault and Live Market Reality sections are present
            self.assertIn("[📚 PRIVATE VAULT KNOWLEDGE]", user_msg)
            self.assertIn("Internal Architecture Doc", user_msg)
            self.assertIn("Cache invalidation must use event-driven pub/sub", user_msg)
            self.assertIn("[🌐 LIVE MARKET REALITY (DUCKDUCKGO)]", user_msg)
            self.assertIn("Redis 7.2 introduces cluster sharding improvements", user_msg)

    @patch("src.synthesis.strategy_generator.generate_completion_async", new_callable=AsyncMock)
    @patch("src.ingestion.embedder.get_embedder")
    async def test_run_librarian_web_search_failure_resilience(self, mock_get_embedder, mock_llm):
        """Web search timeout or network error should NOT abort the Librarian"""
        mock_llm.return_value = "Vault-only synthesis."

        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 768)
        mock_get_embedder.return_value = mock_embedder

        mock_db = AsyncMock()
        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item1.title = "Internal Note"
        mock_item1.source_url = None
        mock_item1.raw_text = "Some raw text"

        exec_results = [
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_item1])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        ]
        mock_db.execute = AsyncMock(side_effect=exec_results)

        # DDGS throws TimeoutError
        with patch("duckduckgo_search.DDGS.text", side_effect=TimeoutError("DDGS connection timed out")):
            result = await self.engine.run_librarian(
                query="Scaling Kafka brokers",
                db=mock_db
            )
            self.assertEqual(result, "Vault-only synthesis.")
            messages = mock_llm.call_args[1]["messages"]
            user_msg = messages[1]["content"]
            self.assertIn("No live market search results retrieved.", user_msg)

    @patch("src.synthesis.strategy_generator.generate_completion_async", new_callable=AsyncMock)
    @patch("src.ingestion.embedder.get_embedder")
    async def test_spar_kata_disambiguation_and_execution(self, mock_get_embedder, mock_llm):
        mock_llm.return_value = "On Kata #1: Your assumption that Redis handles persistence without replica lag is fragile."

        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 768)
        mock_get_embedder.return_value = mock_embedder

        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.title = "Distributed Transactions"
        mock_brick = MagicMock()
        mock_brick.core_thesis = "2PC has high latency"
        mock_brick.critical_pointers = ["Use Saga pattern"]

        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_item])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_brick))
        ])

        forge_text = (
            "🥋 Quick Kata #1: Distributed Cache Failure\n"
            "Scenario: Cache goes down.\n\n"
            "🥋 Quick Kata #2: Event Loop Starvation\n"
            "Scenario: Node.js worker blocked."
        )

        result = await self.engine.spar_kata(
            forge_text=forge_text,
            user_message="For Kata 1, I would add a circuit breaker with local LRU memory cache.",
            db=mock_db,
            focus_state="High availability"
        )

        self.assertIn("Kata #1", result)
        mock_llm.assert_called_once()
        self.assertEqual(mock_llm.call_args[0][0], Tier.PRO.value)


class TestAdversarialForagerJob(unittest.IsolatedAsyncioTestCase):
    """Adversarial tests for forager_job logic, signal filter, and concurrency"""

    @patch("src.jobs.forager_job.generate_completion_async", new_callable=AsyncMock)
    async def test_is_high_signal(self, mock_llm):
        from src.jobs.forager_job import is_high_signal

        # Test positive signal
        mock_llm.return_value = "YES. This is an in-depth technical analysis."
        self.assertTrue(await is_high_signal("Postgres B-Tree Internals", "Deep dive into page layout and lock contention."))

        # Test negative signal (low density)
        mock_llm.return_value = "NO. This is a generic marketing listicle."
        self.assertFalse(await is_high_signal("Top 10 Tech Trends 2026", "Check out these cool tools!"))

        # Test exception resilience (fails closed to protect shadow pool from unvetted link clutter)
        mock_llm.side_effect = Exception("LLM rate limit reached")
        self.assertFalse(await is_high_signal("Unknown Paper", "Abstract"))

    @patch("src.jobs.forager_job.UniversalLinkParser")
    @patch("src.jobs.forager_job.is_high_signal", new_callable=AsyncMock)
    @patch("src.jobs.forager_job.generate_completion_async", new_callable=AsyncMock)
    @patch("src.jobs.forager_job.SessionLocal")
    async def test_run_forager_execution_flow(self, mock_session_local, mock_llm, mock_signal, mock_parser_cls):
        from src.jobs.forager_job import run_forager

        # Mock DB session for InterestVector
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db

        mock_target = MagicMock()
        mock_target.domain = "distributed_databases"
        mock_target.is_blind_spot = True
        mock_target.momentum = 0.8
        mock_target.weight = 0.95

        exec_mock = MagicMock()
        exec_mock.scalars.return_value.all.return_value = [mock_target]
        mock_db.execute.return_value = exec_mock

        # Mock query generation from LLM
        mock_llm.return_value = (
            "site:github.blog distributed database consensus raft\n"
            "site:arxiv.org transactional consistency distributed systems"
        )

        # Mock signal check
        mock_signal.return_value = True

        # Mock parser instance
        mock_parser_instance = MagicMock()
        mock_parser_instance.process_url = AsyncMock()
        mock_parser_cls.return_value = mock_parser_instance

        # Mock DDGS text and video results
        mock_articles = [
            {"title": "Raft in Production", "body": "Architecture of Raft consensus", "href": "https://github.blog/raft"}
        ]
        mock_videos = [
            {"title": "Distributed Systems", "content": "https://youtube.com/watch?v=xyz123"}
        ]

        with patch("duckduckgo_search.DDGS.text", return_value=mock_articles), \
             patch("duckduckgo_search.DDGS.videos", return_value=mock_videos):

            await run_forager()

            # Verify parser was called with ingestion_mode='auto'
            mock_parser_instance.process_url.assert_called()
            call_args_list = mock_parser_instance.process_url.call_args_list
            for call in call_args_list:
                self.assertEqual(call[1]["ingestion_mode"], "auto")


class TestAdversarialTelegramScheduler(unittest.TestCase):
    """Verify APScheduler registration in telegram_bot post_init"""

    @patch("src.delivery.telegram_bot.AsyncIOScheduler")
    def test_post_init_scheduler_registration(self, mock_scheduler_cls):
        import pytz
        from src.delivery.telegram_bot import post_init

        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        mock_app = MagicMock()
        mock_app.bot.set_my_commands = AsyncMock()

        # Run post_init
        asyncio.run(post_init(mock_app))

        # Check timezone is Asia/Kolkata
        mock_scheduler_cls.assert_called_with(timezone=pytz.timezone("Asia/Kolkata"))

        # Check registered jobs
        self.assertEqual(mock_scheduler.add_job.call_count, 2)
        jobs = [c[0] for c in mock_scheduler.add_job.call_args_list]

        # Job 1: Forge at 8:00 AM
        self.assertEqual(jobs[0][1], "cron")
        self.assertEqual(mock_scheduler.add_job.call_args_list[0][1], {"hour": 8, "minute": 0})
        self.assertEqual(jobs[0][0].__name__, "scheduled_forge")

        # Job 2: Forager at 2:00 AM
        self.assertEqual(jobs[1][1], "cron")
        self.assertEqual(mock_scheduler.add_job.call_args_list[1][1], {"hour": 2, "minute": 0})
        self.assertEqual(jobs[1][0].__name__, "scheduled_forager")

        # Verify scheduler started
        mock_scheduler.start.assert_called_once()


class TestAdversarialClientInitialization(unittest.TestCase):
    """Verify safe client initialization and import stability across all generators"""

    def test_safe_imports_with_empty_or_none_api_key(self):
        with patch("src.config.settings.gemini_api_key", None):
            import importlib
            import src.synthesis.kata_generator as kg
            import src.synthesis.aphorism_generator as ag
            import src.synthesis.inversion_generator as ig
            import src.synthesis.suggestion_curator as sc

            importlib.reload(kg)
            importlib.reload(ag)
            importlib.reload(ig)
            importlib.reload(sc)

            self.assertIsNone(kg.client)
            self.assertIsNone(ag.client)
            self.assertIsNone(ig.client)
            self.assertIsNone(sc.client)

    def test_safe_imports_with_valid_api_key(self):
        with patch("src.config.settings.gemini_api_key", "test_mock_api_key_12345"):
            import importlib
            import src.synthesis.kata_generator as kg
            import src.synthesis.aphorism_generator as ag
            import src.synthesis.inversion_generator as ig
            import src.synthesis.suggestion_curator as sc

            importlib.reload(kg)
            importlib.reload(ag)
            importlib.reload(ig)
            importlib.reload(sc)

            self.assertIsNotNone(kg.client)
            self.assertIsNotNone(ag.client)
            self.assertIsNotNone(ig.client)
            self.assertIsNotNone(sc.client)


if __name__ == "__main__":
    unittest.main()
