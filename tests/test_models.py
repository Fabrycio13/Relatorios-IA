import unittest
from src.core.models import Tweet, GitHubRepo, ResearchPaper

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

if __name__ == "__main__":
    unittest.main()
