import os
import sys
import unittest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

# Ensure root in sys.path
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.synthesis.strategy_generator import extract_relevant_snippets, DualLayerContextEngine
from src.jobs.forager_job import is_high_signal
from src.config import Tier

class TestAIIntegrations(unittest.IsolatedAsyncioTestCase):

    def test_extract_relevant_snippets_empty_and_short(self):
        # Empty text / empty query
        self.assertEqual(extract_relevant_snippets("", "query"), [])
        self.assertEqual(extract_relevant_snippets("some text", ""), [])
        
        # Text shorter than window_size
        short_text = "This is a short note on AI systems architecture."
        self.assertEqual(extract_relevant_snippets(short_text, "systems"), [short_text])

    def test_extract_relevant_snippets_zero_token_bloat(self):
        # Text with 1 matching passage and lots of irrelevant filler
        filler_before = "filler introductory text " * 120
        match_section = "critical latency bottleneck in postgres pgvector index scaling "
        filler_after = "irrelevant concluding commentary " * 120
        full_text = filler_before + match_section + filler_after
        
        # When querying for latency bottleneck
        snippets = extract_relevant_snippets(full_text, "latency bottleneck pgvector", window_size=250, top_k=3)
        
        # Verify it returns non-zero score matches without padding with irrelevant 0-score windows
        self.assertTrue(len(snippets) >= 1)
        self.assertTrue(any("latency bottleneck" in s for s in snippets))
        # Ensure snippet word length respects window_size (<= 250 words)
        for s in snippets:
            self.assertLessEqual(len(s.split()), 250)

    def test_extract_relevant_snippets_no_matches_fallback(self):
        full_text = "arbitrary text segment " * 300
        snippets = extract_relevant_snippets(full_text, "unrelated query terms", window_size=250, top_k=3)
        # Should return exactly 1 fallback window (opening context) rather than 3 bloated windows
        self.assertEqual(len(snippets), 1)
        self.assertLessEqual(len(snippets[0].split()), 250)

    @patch('src.jobs.forager_job.generate_completion_async', new_callable=AsyncMock)
    async def test_is_high_signal_strict_parsing(self, mock_llm):
        # Positive cases
        mock_llm.return_value = "YES"
        self.assertTrue(await is_high_signal("Deep Architecture", "Technical analysis of distributed consensus"))
        
        mock_llm.return_value = "YES. This is a seminal engineering post."
        self.assertTrue(await is_high_signal("Deep Architecture", "Technical analysis"))

        # Negative cases
        mock_llm.return_value = "NO"
        self.assertFalse(await is_high_signal("Top 10 Tools", "Superficial listicle"))

        mock_llm.return_value = "NO. This was published yesterday and lacks technical depth."
        self.assertFalse(await is_high_signal("Hype article", "Yesterday news"))

        mock_llm.return_value = "NO: generic marketing clickbait"
        self.assertFalse(await is_high_signal("Marketing post", "Click here"))

    @patch('src.synthesis.strategy_generator.generate_completion_async', new_callable=AsyncMock)
    async def test_run_librarian_prompt_contract(self, mock_llm):
        mock_llm.return_value = "Strategic advice answering founder question."
        engine = DualLayerContextEngine(root_dir=str(root_path))
        
        # Mock DB
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        with patch('src.ingestion.embedder.get_embedder') as mock_get_embedder:
            mock_embedder = AsyncMock()
            mock_embedder.embed_text.return_value = [0.1] * 768
            mock_get_embedder.return_value = mock_embedder
            
            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
                mock_thread.return_value = [
                    {'title': 'Market Report', 'href': 'https://example.com/report', 'body': 'Market consensus is moving fast.'}
                ]
                res = await engine.run_librarian("What is the state of agentic workflows?", mock_db)
                
                # Check call args to generate_completion_async
                self.assertTrue(mock_llm.called)
                call_args = mock_llm.call_args
                tier_used = call_args[0][0]
                messages = call_args[1]['messages']
                system_prompt = messages[0]['content']
                user_prompt = messages[1]['content']
                
                # 1. Tier used must be PRO
                self.assertEqual(tier_used, Tier.PRO.value)
                # 2. Output badges enforced in system prompt
                self.assertIn("[📚 Private Vault]", system_prompt)
                self.assertIn("[🌐 Live Market Reality]", system_prompt)
                # 3. User content structured properly
                self.assertIn("=== [📚 PRIVATE VAULT KNOWLEDGE] ===", user_prompt)
                self.assertIn("=== [🌐 LIVE MARKET REALITY (DUCKDUCKGO)] ===", user_prompt)

    @patch('src.synthesis.strategy_generator.generate_completion_async', new_callable=AsyncMock)
    async def test_ask_brick_prompt_contract(self, mock_llm):
        mock_llm.return_value = "Punchy strategic deep-dive."
        engine = DualLayerContextEngine(root_dir=str(root_path))
        
        brick_text = "Core Thesis: Postgres pgvector scales well with IVFFlat.\nMechanics: Partitioning."
        question = "What about memory usage under heavy indexing?"
        
        res = await engine.ask_brick(brick_text, question)
        
        self.assertTrue(mock_llm.called)
        tier_used = mock_llm.call_args[0][0]
        self.assertEqual(tier_used, Tier.PRO.value)

if __name__ == '__main__':
    unittest.main()
