import os
import tempfile
import unittest
from pathlib import Path
from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch

class TestModels(unittest.TestCase):

    def test_tweet_serialization(self):
        t = Tweet(
            author_name="Matt Pocock",
            author_handle="@mattpocockuk",
            timestamp="2026-10-21T10:00:00Z",
            text="AI coding agents are evolving fast.",
            url="https://x.com/mattpocockuk/status/123",
            likes="1500",
            reposts="250",
            replies="50",
            views="45000",
            external_links=["https://github.com/example/repo"]
        )
        d = t.to_dict()
        self.assertEqual(d["author_name"], "Matt Pocock")
        self.assertEqual(d["likes"], "1500")

        t2 = Tweet.from_dict(d)
        self.assertEqual(t2.author_handle, "@mattpocockuk")
        self.assertEqual(t2.external_links, ["https://github.com/example/repo"])

    def test_tweet_sanitization_against_prompt_injection(self):
        malicious_text = "Normal text\x00\x08 with hidden \x1b control \t\t chars and multiple   spaces."
        t = Tweet(
            author_name="Bad Actor",
            author_handle="@badactor",
            timestamp="",
            text=malicious_text,
            url=""
        )
        cleaned = t.sanitized_text()
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\x08", cleaned)
        self.assertNotIn("\x1b", cleaned)
        self.assertNotIn("   ", cleaned)
        self.assertIn("Normal text with hidden control chars and multiple spaces.", cleaned)

    def test_github_repo_serialization(self):
        repo = GitHubRepo(
            name="blender-mcp",
            full_name="org/blender-mcp",
            stars=950,
            description="Blender AI MCP Addon",
            language="Python",
            url="https://github.com/org/blender-mcp",
            topics=["mcp", "ai-agent"]
        )
        d = repo.to_dict()
        self.assertEqual(d["stars"], 950)
        repo2 = GitHubRepo.from_dict(d)
        self.assertEqual(repo2.full_name, "org/blender-mcp")

    def test_research_paper_serialization(self):
        paper = ResearchPaper(
            title="Training the Whole Agent",
            arxiv_id="2610.28069",
            summary="Novel framework for training harness and policy jointly.",
            authors=["Alice", "Bob"],
            upvotes=42,
            url="https://huggingface.co/papers/2610.28069"
        )
        d = paper.to_dict()
        self.assertEqual(d["arxiv_id"], "2610.28069")
        paper2 = ResearchPaper.from_dict(d)
        self.assertEqual(paper2.title, "Training the Whole Agent")
        self.assertEqual(len(paper2.authors), 2)

    def test_daily_ingestion_batch_defaults_and_is_empty(self):
        batch = DailyIngestionBatch()
        self.assertEqual(batch.tweets, [])
        self.assertEqual(batch.repos, [])
        self.assertEqual(batch.papers, [])
        self.assertTrue(bool(batch.collected_at))
        self.assertTrue(batch.is_empty())

        # Popula apenas uma das listas e valida que não está mais vazio
        batch.repos.append(
            GitHubRepo(name="test", full_name="org/test", stars=1, description="desc", language="Py", url="http://x")
        )
        self.assertFalse(batch.is_empty())

    def test_daily_ingestion_batch_serialization_roundtrip(self):
        t = Tweet(
            author_name="Matt Pocock",
            author_handle="@mattpocockuk",
            timestamp="2026-10-21T10:00:00Z",
            text="AI coding agents are evolving fast.",
            url="https://x.com/mattpocockuk/status/123",
            likes="1500",
            reposts="250",
            replies="50",
            views="45000",
            external_links=[]
        )
        r = GitHubRepo(
            name="blender-mcp",
            full_name="org/blender-mcp",
            stars=950,
            description="Blender AI MCP Addon",
            language="Python",
            url="https://github.com/org/blender-mcp",
            topics=["mcp"]
        )
        p = ResearchPaper(
            title="Training the Whole Agent",
            arxiv_id="2610.28069",
            summary="Novel framework for training harness and policy jointly.",
            authors=["Alice"],
            upvotes=42,
            url="https://huggingface.co/papers/2610.28069"
        )
        original = DailyIngestionBatch(
            tweets=[t],
            repos=[r],
            papers=[p],
            collected_at="2026-10-27T08:00:00"
        )
        d = original.to_dict()
        self.assertEqual(len(d["tweets"]), 1)
        self.assertEqual(len(d["repos"]), 1)
        self.assertEqual(len(d["papers"]), 1)
        self.assertEqual(d["collected_at"], "2026-10-27T08:00:00")

        restored = DailyIngestionBatch.from_dict(d)
        self.assertEqual(restored.collected_at, "2026-10-27T08:00:00")
        self.assertEqual(len(restored.tweets), 1)
        self.assertEqual(restored.tweets[0].author_handle, "@mattpocockuk")
        self.assertEqual(len(restored.repos), 1)
        self.assertEqual(restored.repos[0].name, "blender-mcp")
        self.assertEqual(len(restored.papers), 1)
        self.assertEqual(restored.papers[0].arxiv_id, "2610.28069")

    def test_daily_ingestion_batch_save_and_load_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            t = Tweet(
                author_name="Alice", author_handle="@alice", timestamp="", text="Hi", url="http://x"
            )
            r = GitHubRepo(
                name="cool-repo", full_name="org/cool-repo", stars=10, description="", language="Python", url="http://gh"
            )
            p = ResearchPaper(
                title="Agent Paper", arxiv_id="1234", summary="desc", authors=["A"], upvotes=5, url="http://hf"
            )
            batch = DailyIngestionBatch(
                tweets=[t],
                repos=[r],
                papers=[p],
                collected_at="2026-10-27T10:00:00"
            )

            # Salva snapshot
            batch.save_snapshot(tmp_path)

            # Valida arquivos gerados no formato array JSON compatível
            self.assertTrue((tmp_path / "tweets_coletados.json").exists())
            self.assertTrue((tmp_path / "github_trending.json").exists())
            self.assertTrue((tmp_path / "hf_papers.json").exists())
            self.assertTrue((tmp_path / "snapshot_metadata.json").exists())

            # Garante que nenhum arquivo temporário (.tmp) restou
            tmp_files = list(tmp_path.glob("*.tmp"))
            self.assertEqual(len(tmp_files), 0)

            # Carrega snapshot e compara
            loaded = DailyIngestionBatch.load_snapshot(tmp_path)
            self.assertFalse(loaded.is_empty())
            self.assertEqual(len(loaded.tweets), 1)
            self.assertEqual(loaded.tweets[0].author_name, "Alice")
            self.assertEqual(len(loaded.repos), 1)
            self.assertEqual(loaded.repos[0].name, "cool-repo")
            self.assertEqual(len(loaded.papers), 1)
            self.assertEqual(loaded.papers[0].title, "Agent Paper")
            self.assertEqual(loaded.collected_at, "2026-10-27T10:00:00")

    def test_daily_ingestion_batch_load_snapshot_graceful_missing_and_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 1. Diretório vazio ou inexistente
            empty_loaded = DailyIngestionBatch.load_snapshot(tmp_path / "inexistente")
            self.assertTrue(empty_loaded.is_empty())
            self.assertEqual(empty_loaded.tweets, [])

            # 2. Arquivo corrompido (JSON inválido)
            corrupt_file = tmp_path / "tweets_coletados.json"
            corrupt_file.write_text("{este_nao_e_um_json_valido:", encoding="utf-8")

            resilient_batch = DailyIngestionBatch.load_snapshot(tmp_path)
            self.assertEqual(resilient_batch.tweets, [])
            self.assertEqual(resilient_batch.repos, [])
            self.assertEqual(resilient_batch.papers, [])

            # 3. Snapshot legado sem snapshot_metadata.json (deve usar mtime como fallback)
            corrupt_file.unlink()
            good_file = tmp_path / "tweets_coletados.json"
            good_file.write_text("[]", encoding="utf-8")
            legacy_batch = DailyIngestionBatch.load_snapshot(str(tmp_path))
            self.assertTrue(legacy_batch.is_empty())
            self.assertTrue(bool(legacy_batch.collected_at))

    def test_daily_ingestion_batch_save_snapshot_single_source(self):
        """Valida que save_snapshot com source definido grava apenas o arquivo da fonte selecionada."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Grava previamente tweets de ontem
            old_tweets_file = tmp_path / "tweets_coletados.json"
            old_tweets_file.write_text('[{"text": "ontem"}]', encoding="utf-8")

            # Salva apenas repos
            r = GitHubRepo(name="new-repo", full_name="org/new-repo", stars=100, description="", language="Python", url="")
            batch = DailyIngestionBatch(repos=[r], collected_at="2026-10-27T12:00:00")
            batch.save_snapshot(tmp_path, source="github")

            # Garante que tweets não foi sobrescrito
            self.assertEqual(old_tweets_file.read_text(encoding="utf-8"), '[{"text": "ontem"}]')
            # Garante que repos foi criado
            self.assertTrue((tmp_path / "github_trending.json").exists())
            # Garante que papers não foi criado
            self.assertFalse((tmp_path / "hf_papers.json").exists())

    def test_daily_ingestion_batch_from_dict_defaults(self):
        batch = DailyIngestionBatch.from_dict({})
        self.assertTrue(batch.is_empty())
        self.assertTrue(bool(batch.collected_at))

if __name__ == "__main__":
    unittest.main()
