import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from src.core.models import (
    Tweet,
    GitHubRepo,
    ResearchPaper,
    SourceStatus,
    SourceCollectionResult,
)


class TestDomainModelsImmutabilityAndSerialization(unittest.TestCase):
    """Testes de imutabilidade profunda e serialização com tuplas nativas e listas JSON."""

    def test_tweet_is_frozen_with_native_tuple(self):
        tweet = Tweet(
            author_name="Matt Pocock",
            author_handle="@mattpocockuk",
            timestamp="2026-10-21T10:00:00Z",
            text="AI coding agents are evolving fast.",
            url="https://x.com/mattpocockuk/status/123",
            likes="1500",
            reposts="250",
            replies="50",
            views="45000",
            external_links=["https://github.com/example/repo"],
        )
        with self.assertRaises(FrozenInstanceError):
            tweet.likes = "2000"  # type: ignore

        # Valida que external_links é tuple nativa e imutável
        self.assertIs(type(tweet.external_links), tuple)
        with self.assertRaises(AttributeError):
            tweet.external_links.append("https://evil.com")  # type: ignore

    def test_github_repo_is_frozen_with_native_tuple(self):
        repo = GitHubRepo(
            name="blender-mcp",
            full_name="org/blender-mcp",
            stars=950,
            description="Blender AI MCP Addon",
            language="Python",
            url="https://github.com/org/blender-mcp",
            topics=["mcp", "ai-agent"],
        )
        with self.assertRaises(FrozenInstanceError):
            repo.stars = 1000  # type: ignore

        self.assertIs(type(repo.topics), tuple)
        with self.assertRaises(AttributeError):
            repo.topics.append("new-topic")  # type: ignore

    def test_research_paper_is_frozen_with_native_tuple(self):
        paper = ResearchPaper(
            title="Training the Whole Agent",
            arxiv_id="2610.28069",
            summary="Novel framework for training harness and policy jointly.",
            authors=["Alice", "Bob"],
            upvotes=42,
            url="https://huggingface.co/papers/2610.28069",
        )
        with self.assertRaises(FrozenInstanceError):
            paper.upvotes = 43  # type: ignore

        self.assertIs(type(paper.authors), tuple)
        with self.assertRaises(AttributeError):
            paper.authors.append("Charlie")  # type: ignore

    def test_to_dict_produces_native_python_lists_for_json(self):
        tweet = Tweet(
            author_name="A",
            author_handle="@a",
            timestamp="2026-11-12T08:00:00Z",
            text="Hello world",
            url="https://x.com/a/1",
            external_links=("https://link1.com", "https://link2.com"),
        )
        d = tweet.to_dict()
        # to_dict deve retornar lista Python normal para compatibilidade JSON
        self.assertIs(type(d["external_links"]), list)
        self.assertEqual(d["external_links"], ["https://link1.com", "https://link2.com"])

        repo = GitHubRepo(
            name="r",
            full_name="o/r",
            stars=10,
            description="d",
            language="py",
            url="http",
            topics=("t1", "t2"),
        )
        d_repo = repo.to_dict()
        self.assertIs(type(d_repo["topics"]), list)
        self.assertEqual(d_repo["topics"], ["t1", "t2"])

        paper = ResearchPaper(
            title="P",
            arxiv_id="1",
            summary="s",
            authors=("A1", "A2"),
            upvotes=5,
            url="http",
        )
        d_paper = paper.to_dict()
        self.assertIs(type(d_paper["authors"]), list)
        self.assertEqual(d_paper["authors"], ["A1", "A2"])

    def test_from_dict_and_roundtrip_type_integrity(self):
        # Roundtrip Tweet
        data_tweet = {
            "author_name": "Author",
            "author_handle": "@handle",
            "timestamp": "2026-11-12T08:00:00Z",
            "text": "Tweet text",
            "url": "https://x.com/post/1",
            "external_links": ["https://site.com"],
        }
        t = Tweet.from_dict(data_tweet)
        self.assertIs(type(t.external_links), tuple)
        self.assertEqual(t.external_links, ("https://site.com",))

        d_back = t.to_dict()
        self.assertIs(type(d_back["external_links"]), list)
        self.assertEqual(d_back["external_links"], ["https://site.com"])


class TestSourceStatusEnum(unittest.TestCase):
    """Testes do enumerador SourceStatus."""

    def test_source_status_values(self):
        self.assertEqual(SourceStatus.SUCCESS, "success")
        self.assertEqual(SourceStatus.EMPTY, "empty")
        self.assertEqual(SourceStatus.PARTIAL, "partial")
        self.assertEqual(SourceStatus.FAILED, "failed")
        self.assertEqual(SourceStatus.NOT_RUN, "not_run")
        self.assertIsInstance(SourceStatus.SUCCESS, str)


class TestSourceCollectionResultInvariants(unittest.TestCase):
    """Testes completos dos invariantes e do contrato de operações de SourceCollectionResult."""

    def test_instancia_valida_success(self):
        res = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.SUCCESS,
            items=("tweet1",),
            successful_operations=("feed_scroll", "profile_scan"),
            failed_operations=(),
        )
        self.assertEqual(res.source_name, "twitter")
        self.assertEqual(res.status, SourceStatus.SUCCESS)
        self.assertEqual(res.items, ("tweet1",))
        self.assertTrue(res.has_usable_data)
        self.assertEqual(res.successful_operations, ("feed_scroll", "profile_scan"))
        self.assertEqual(res.failed_operations, ())
        self.assertIsNone(res.error_message)
        self.assertFalse(res.rate_limited)
        self.assertIsInstance(res.collected_at, datetime)

    def test_is_frozen(self):
        res = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.EMPTY,
            items=(),
            successful_operations=("feed_scroll",),
            failed_operations=(),
        )
        with self.assertRaises(FrozenInstanceError):
            res.status = SourceStatus.SUCCESS  # type: ignore

    def test_defensive_conversion_to_native_tuples(self):
        res = SourceCollectionResult(
            source_name="generic",
            status=SourceStatus.SUCCESS,
            items=["item1", "item2"],  # type: ignore
            successful_operations=["op1", "op2"],  # type: ignore
            failed_operations=[],  # type: ignore
        )
        self.assertIs(type(res.items), tuple)
        self.assertEqual(res.items, ("item1", "item2"))
        self.assertIs(type(res.successful_operations), tuple)
        self.assertEqual(res.successful_operations, ("op1", "op2"))
        self.assertIs(type(res.failed_operations), tuple)
        self.assertEqual(res.failed_operations, ())

    # --- INVARIANTES: SUCCESS ---

    def test_success_without_items_raises_value_error(self):
        # SUCCESS exige itens. Se não há itens, o status correto é EMPTY.
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.SUCCESS,
                items=(),
                successful_operations=("op1",),
            )

    def test_success_with_failed_operations_raises_value_error(self):
        # SUCCESS não pode ter operações com falha. Se houve falhas, o status é PARTIAL.
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.SUCCESS,
                items=("item1",),
                successful_operations=("op1",),
                failed_operations=("op2_failed",),
            )

    def test_success_without_successful_operations_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.SUCCESS,
                items=("item1",),
                successful_operations=(),
            )

    # --- INVARIANTES: EMPTY ---

    def test_empty_with_items_raises_value_error(self):
        # EMPTY requer rigorosamente 0 itens
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.EMPTY,
                items=("item1",),
                successful_operations=("op1",),
            )

    def test_empty_with_failed_operations_raises_value_error(self):
        # EMPTY é sucesso sem dados novos; não pode ter falhas operacionais
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.EMPTY,
                items=(),
                successful_operations=("op1",),
                failed_operations=("op_fail",),
            )

    def test_empty_without_successful_operations_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.EMPTY,
                items=(),
                successful_operations=(),
            )

    # --- INVARIANTES: PARTIAL ---

    def test_partial_without_successful_operations_raises_value_error(self):
        # PARTIAL exige que pelo menos uma operação tenha tido sucesso
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.PARTIAL,
                items=("item1",),
                successful_operations=(),
                failed_operations=("op_fail",),
                error_message="Falha parcial",
            )

    def test_partial_without_failed_operations_raises_value_error(self):
        # PARTIAL exige que pelo menos uma operação tenha falhado
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.PARTIAL,
                items=("item1",),
                successful_operations=("op1",),
                failed_operations=(),
                error_message="Falha parcial",
            )

    def test_partial_without_error_message_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.PARTIAL,
                items=("item1",),
                successful_operations=("op1",),
                failed_operations=("op_fail",),
                error_message=None,
            )

    def test_partial_valid_with_zero_items_preserved(self):
        # Cenário legítimo: operações de sucesso ocorreram (mas retornaram vazio)
        # e outras operações falharam. Tem sucesso, tem falha e 0 itens.
        res = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.PARTIAL,
            items=(),
            successful_operations=("subfonte_a_vazia",),
            failed_operations=("subfonte_b_timeout",),
            error_message="Subfonte B expirou",
        )
        self.assertEqual(res.status, SourceStatus.PARTIAL)
        self.assertEqual(len(res.items), 0)
        self.assertFalse(res.has_usable_data)  # Sem itens utilizáveis

    # --- INVARIANTES: FAILED ---

    def test_failed_with_items_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.FAILED,
                items=("item1",),
                failed_operations=("op1",),
                error_message="Erro fatal",
            )

    def test_failed_with_successful_operations_raises_value_error(self):
        # Se houve operações com sucesso, deve ser classificado como PARTIAL
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=("op1_ok",),
                failed_operations=("op2_fail",),
                error_message="Erro",
            )

    def test_failed_without_failed_operations_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=(),
                failed_operations=(),
                error_message="Erro",
            )

    def test_failed_without_error_message_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=(),
                failed_operations=("op1",),
                error_message=None,
            )

    # --- INVARIANTES: NOT_RUN ---

    def test_not_run_with_items_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.NOT_RUN,
                items=("item1",),
            )

    def test_not_run_with_operations_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.NOT_RUN,
                items=(),
                successful_operations=("op1",),
            )

        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.NOT_RUN,
                items=(),
                failed_operations=("op1",),
            )

    def test_not_run_with_error_message_raises_value_error(self):
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.NOT_RUN,
                items=(),
                error_message="Não deveria ter erro",
            )

    # --- VALIDAÇÃO DE TIPOS DE OPERAÇÕES E STATUS ---

    def test_reject_invalid_status_types_and_unknown_strings(self):
        # Rejeita strings desconhecidas
        with self.assertRaises(ValueError):
            SourceCollectionResult(
                source_name="tw",
                status="unknown_status",  # type: ignore
                items=(),
            )

        # Rejeita tipos não-SourceStatus
        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="tw",
                status=123,  # type: ignore
                items=(),
            )

        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="tw",
                status=None,  # type: ignore
                items=(),
            )

        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="tw",
                status=True,  # type: ignore
                items=(),
            )

    def test_operations_must_be_strings_or_sequence_of_strings(self):
        # Rejeita inteiros ou booleanos passados como operações
        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="gh",
                status=SourceStatus.SUCCESS,
                items=("item",),
                successful_operations=1,  # type: ignore
            )

        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="gh",
                status=SourceStatus.SUCCESS,
                items=("item",),
                successful_operations=(True, "op1"),  # type: ignore
            )

        with self.assertRaises(TypeError):
            SourceCollectionResult(
                source_name="gh",
                status=SourceStatus.FAILED,
                items=(),
                failed_operations=(123,),  # type: ignore
                error_message="Erro",
            )


if __name__ == "__main__":
    unittest.main()
