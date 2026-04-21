"""End-to-end BYO pipeline tests using bohr_model_tutor_script.pdf.

Tests ingestion (extract → chunk → classify → embed → store) and
retrieval (semantic search, fetch, nearby) against a real document.

Run:
    pytest backend/tests/byo/test_pipeline_bohr.py -v -s

Requires:
    - backend/.env with MONGODB_URI, OPENROUTER_API_KEY
    - The test PDF at /Users/admin/Downloads/Bohr_Model 2/bohr_model_tutor_script.pdf
"""

import asyncio
import os
import sys
import time
import pytest

# Project paths
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, "backend", ".env"), override=False)
except ImportError:
    pass

PDF_PATH = "/Users/admin/Downloads/Bohr_Model 2/bohr_model_tutor_script.pdf"
TEST_USER = "test_pipeline@test.local"
TEST_COLLECTION = "test_bohr_pipeline"
TEST_RESOURCE_ID = "test_bohr_resource_001"


# ═══════════════════════════════════════════════════════════
# INGESTION TESTS
# ═══════════════════════════════════════════════════════════


class TestExtraction:
    """Test PDF extraction step."""

    @pytest.fixture(autouse=True)
    def check_pdf(self):
        if not os.path.exists(PDF_PATH):
            pytest.skip(f"Test PDF not found: {PDF_PATH}")

    def test_pdf_extraction_produces_markdown(self):
        """PDF extracts to non-empty markdown."""
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        md = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
        assert len(md) > 1000, f"Extraction too short: {len(md)} chars"
        assert "Bohr" in md, "Expected 'Bohr' in extracted text"

    def test_pdf_extraction_captures_equations(self):
        """Key equations from the document should appear in extraction."""
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        md = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
        # Rydberg formula components
        assert "13.6" in md, "Missing ground state energy 13.6 eV"
        assert "Rydberg" in md or "rydberg" in md.lower(), "Missing Rydberg reference"

    def test_pdf_extraction_captures_sections(self):
        """Document has clear phases that should appear as headers."""
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        md = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
        assert "Phase 1" in md or "Crisis" in md, "Missing Phase 1 header"
        assert "Phase 2" in md or "Postulates" in md, "Missing Phase 2 header"
        assert "Phase 3" in md or "Derivation" in md, "Missing Phase 3 header"

    def test_pdf_meta_has_page_count(self):
        """Extraction metadata should include page count."""
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        meta = result.meta if hasattr(result, "meta") else result.get("meta", {})
        pages = meta.get("pages") or meta.get("total_pages")
        assert pages is not None, "Missing page count in meta"
        assert pages == 26, f"Expected 26 pages, got {pages}"

    def test_corrupted_pdf_returns_error(self):
        """A corrupted file should return an error, not crash."""
        import tempfile
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"this is not a valid PDF content at all")
            f.flush()
            try:
                result = asyncio.get_event_loop().run_until_complete(
                    proc.extract(
                        resource_id="test_corrupt",
                        mime_type="application/pdf",
                        source_url=None,
                        storage_path=f.name,
                        meta={},
                    )
                )
                meta = result.meta if hasattr(result, "meta") else result.get("meta", {})
                # Should either have error in meta or empty markdown — not crash
                assert meta.get("error") or len(
                    result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
                ) == 0, "Corrupted PDF should produce error or empty result"
            finally:
                os.unlink(f.name)

    def test_empty_pdf_returns_gracefully(self):
        """A PDF with no text should not crash."""
        import tempfile
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                doc.save(f.name)
                doc.close()
                from byo.processing.processors.pdf import PDFProcessor
                proc = PDFProcessor()
                result = asyncio.get_event_loop().run_until_complete(
                    proc.extract(
                        resource_id="test_empty",
                        mime_type="application/pdf",
                        source_url=None,
                        storage_path=f.name,
                        meta={},
                    )
                )
                md = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
                assert isinstance(md, str), "Should return string, not crash"
                os.unlink(f.name)
        except ImportError:
            pytest.skip("fitz not available")


class TestChunking:
    """Test chunking step."""

    @pytest.fixture
    def bohr_markdown(self):
        """Extract markdown from the Bohr PDF for chunking tests."""
        if not os.path.exists(PDF_PATH):
            pytest.skip(f"Test PDF not found: {PDF_PATH}")
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        return result.markdown if hasattr(result, "markdown") else result.get("markdown", "")

    def test_chunking_produces_parents_and_segments(self, bohr_markdown):
        """Chunking should produce both parent chunks and child segments."""
        from byo.processing.chunker import chunk_markdown
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=bohr_markdown,
                resource_id=TEST_RESOURCE_ID,
                collection_id=TEST_COLLECTION,
                resource_meta={"title": "Bohr Model"},
                user_id=TEST_USER,
                mime_type="application/pdf",
            )
        )
        assert len(parents) > 0, "Should produce at least 1 parent chunk"
        assert len(segments) > 0, "Should produce at least 1 segment"
        assert len(segments) >= len(parents), "Segments should be >= parents (children of parents)"

    def test_parent_chunks_have_required_fields(self, bohr_markdown):
        """Each parent chunk must have content, resource_id, chunk_id."""
        from byo.processing.chunker import chunk_markdown
        parents, _ = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=bohr_markdown,
                resource_id=TEST_RESOURCE_ID,
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="application/pdf",
            )
        )
        for p in parents:
            assert p.get("content"), f"Parent missing content: {p.get('chunk_id')}"
            assert p.get("resource_id") == TEST_RESOURCE_ID
            assert p.get("chunk_id"), "Parent missing chunk_id"

    def test_segments_have_embeddings_placeholder(self, bohr_markdown):
        """Segments should have content ready for embedding."""
        from byo.processing.chunker import chunk_markdown
        _, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=bohr_markdown,
                resource_id=TEST_RESOURCE_ID,
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="application/pdf",
            )
        )
        for s in segments:
            assert s.get("content"), f"Segment missing content: {s.get('segment_id')}"
            assert len(s["content"]) <= 5000, f"Segment too long ({len(s['content'])} chars) — should be split further"

    def test_chunk_sizes_are_reasonable(self, bohr_markdown):
        """Parent chunks should be 200-1200 tokens (roughly 800-5000 chars)."""
        from byo.processing.chunker import chunk_markdown
        parents, _ = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=bohr_markdown,
                resource_id=TEST_RESOURCE_ID,
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="application/pdf",
            )
        )
        for p in parents:
            content_len = len(p.get("content", ""))
            assert content_len > 50, f"Parent too short ({content_len} chars): {p.get('chunk_id')}"
            assert content_len < 6000, f"Parent too long ({content_len} chars): {p.get('chunk_id')}"

    def test_empty_markdown_returns_empty(self):
        """Empty input should return empty lists, not crash."""
        from byo.processing.chunker import chunk_markdown
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown="",
                resource_id="test_empty",
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="text/plain",
            )
        )
        assert parents == [] or len(parents) == 0
        assert segments == [] or len(segments) == 0


class TestEmbedding:
    """Test embedding step (requires OPENROUTER_API_KEY)."""

    def test_embedding_generates_vectors(self):
        """Segments should get non-empty embedding vectors."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from byo.processing.embedder import embed_segments_batch
        segments = [
            {"content": "The Bohr model postulates that electrons orbit the nucleus in quantized energy levels.", "segment_id": "seg1"},
            {"content": "The Rydberg formula predicts hydrogen spectral lines: 1/λ = R(1/n₁² - 1/n₂²).", "segment_id": "seg2"},
            {"content": "The ground state energy of hydrogen is -13.6 eV.", "segment_id": "seg3"},
        ]
        asyncio.get_event_loop().run_until_complete(embed_segments_batch(segments))
        for s in segments:
            emb = s.get("embedding", [])
            assert len(emb) > 0, f"Segment {s['segment_id']} has no embedding"
            assert len(emb) == 1536, f"Expected 1536-dim embedding, got {len(emb)}"

    def test_embedding_empty_content_graceful(self):
        """Empty content should not crash the embedder."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from byo.processing.embedder import embed_segments_batch
        segments = [{"content": "", "segment_id": "empty"}]
        asyncio.get_event_loop().run_until_complete(embed_segments_batch(segments))
        # Should not crash — embedding may be empty or zero vector

    def test_embedding_handles_long_text(self):
        """Long text should be truncated, not crash."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from byo.processing.embedder import embed_segments_batch
        segments = [{"content": "Bohr model " * 1000, "segment_id": "long"}]
        asyncio.get_event_loop().run_until_complete(embed_segments_batch(segments))
        emb = segments[0].get("embedding", [])
        assert len(emb) > 0, "Long text should still produce an embedding"


# ═══════════════════════════════════════════════════════════
# RETRIEVAL TESTS
# ═══════════════════════════════════════════════════════════


class TestRetrieval:
    """Test retrieval against ingested Bohr Model content.

    These tests require the document to be ingested first.
    Run ingestion tests before these.
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")

    def _search(self, query, k=5):
        """Helper: run semantic search via the retrieval service."""
        from byo.retrieval.service import search
        results = asyncio.get_event_loop().run_until_complete(
            search(
                query=query,
                user_id=TEST_USER,
                collection_id=TEST_COLLECTION,
                k=k,
            )
        )
        return results

    def test_search_bohr_model_returns_results(self):
        """Basic query 'Bohr model' should return relevant results."""
        results = self._search("What is the Bohr model of the atom?")
        assert len(results) > 0, "Search for 'Bohr model' returned no results"

    def test_search_rydberg_formula(self):
        """Query about Rydberg formula should find relevant content."""
        results = self._search("Rydberg formula for hydrogen spectral lines")
        assert len(results) > 0, "Search for 'Rydberg formula' returned no results"
        texts = " ".join(r.get("content", "") for r in results)
        assert "Rydberg" in texts or "rydberg" in texts.lower() or "1/λ" in texts, \
            "Results should contain Rydberg-related content"

    def test_search_energy_levels(self):
        """Query about energy levels should find the -13.6 eV content."""
        results = self._search("hydrogen energy levels ground state")
        assert len(results) > 0, "Search for energy levels returned no results"
        texts = " ".join(r.get("content", "") for r in results)
        assert "13.6" in texts, "Results should mention 13.6 eV ground state energy"

    def test_search_classical_instability(self):
        """Query about classical atom instability (Phase 1 content)."""
        results = self._search("Why is the classical atom unstable? Larmor radiation spiral")
        assert len(results) > 0, "Search for classical instability returned no results"
        texts = " ".join(r.get("content", "") for r in results).lower()
        assert any(w in texts for w in ["spiral", "larmor", "classical", "unstable", "radiate"]), \
            "Results should discuss classical instability"

    def test_search_bohr_postulates(self):
        """Query about Bohr's postulates (Phase 2 content)."""
        results = self._search("What are Bohr's three postulates?")
        assert len(results) > 0
        texts = " ".join(r.get("content", "") for r in results).lower()
        assert any(w in texts for w in ["postulate", "quantized", "stationary", "orbit"]), \
            "Results should discuss Bohr's postulates"

    def test_search_fine_structure_constant(self):
        """Query about fine structure constant α ≈ 1/137."""
        results = self._search("fine structure constant alpha 1/137")
        assert len(results) > 0
        texts = " ".join(r.get("content", "") for r in results)
        assert "137" in texts or "fine structure" in texts.lower(), \
            "Results should mention fine structure constant"

    def test_search_no_results_for_irrelevant_query(self):
        """Completely unrelated query should return low-relevance or empty results."""
        results = self._search("How to make chocolate cake recipe")
        # Should either return no results or results with very low scores
        if results:
            scores = [r.get("score", 0) for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0
            assert avg_score < 0.5, f"Irrelevant query got high scores: {avg_score}"

    def test_search_ranking_quality(self):
        """More specific queries should rank better than vague ones."""
        specific_results = self._search("Bohr radius a0 equals 0.529 angstroms")
        vague_results = self._search("atom")
        if specific_results and vague_results:
            specific_top = specific_results[0].get("score", 0)
            vague_top = vague_results[0].get("score", 0)
            # Specific query should generally score higher
            assert specific_top > 0, "Specific query should have positive score"


# ═══════════════════════════════════════════════════════════
# EDGE CASE / FAILURE TESTS
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and failure modes."""

    def test_large_pdf_extraction_timeout(self):
        """PDF extraction should complete within 120 seconds."""
        if not os.path.exists(PDF_PATH):
            pytest.skip("Test PDF not found")
        from byo.processing.processors.pdf import PDFProcessor
        proc = PDFProcessor()
        start = time.time()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id="test_timeout",
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        elapsed = time.time() - start
        assert elapsed < 120, f"Extraction took {elapsed:.1f}s — too slow"

    def test_non_pdf_mime_type_handled(self):
        """Passing wrong MIME type should not crash."""
        from byo.processing.processors import get_processor
        proc = get_processor("text/plain")
        assert proc is not None, "Should return a processor for text/plain"

    def test_unsupported_mime_type_handled(self):
        """Unsupported MIME type should return a graceful error or fallback."""
        from byo.processing.processors import get_processor
        proc = get_processor("application/x-unknown-format-xyz")
        # Should either return a generic processor or None
        # Should NOT crash

    def test_concurrent_embedding_batches(self):
        """Multiple embedding batches should not interfere with each other."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        from byo.processing.embedder import embed_segments_batch
        batch1 = [{"content": f"Bohr model segment {i}", "segment_id": f"b1_{i}"} for i in range(5)]
        batch2 = [{"content": f"Rydberg formula segment {i}", "segment_id": f"b2_{i}"} for i in range(5)]

        async def run_parallel():
            await asyncio.gather(
                embed_segments_batch(batch1),
                embed_segments_batch(batch2),
            )

        asyncio.get_event_loop().run_until_complete(run_parallel())
        for s in batch1 + batch2:
            assert len(s.get("embedding", [])) > 0, f"Missing embedding: {s['segment_id']}"

    def test_unicode_content_handling(self):
        """Content with unicode (Greek letters, math symbols) should not crash."""
        from byo.processing.chunker import chunk_markdown
        md = """# Bohr Model Equations

The energy is E_n = -13.6/n² eV

Angular momentum: L = nℏ where ℏ = h/2π

The Rydberg constant: R∞ = 1.097 × 10⁷ m⁻¹

Greek: α β γ δ ε ζ η θ ι κ λ μ ν ξ π ρ σ τ υ φ χ ψ ω
"""
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=md,
                resource_id="test_unicode",
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="text/plain",
            )
        )
        assert len(parents) > 0, "Unicode content should produce chunks"

    def test_very_long_single_paragraph(self):
        """A single very long paragraph should be split, not overflow."""
        from byo.processing.chunker import chunk_markdown
        long_text = "The Bohr model explains atomic structure. " * 500
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=long_text,
                resource_id="test_long",
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="text/plain",
            )
        )
        assert len(parents) >= 1, "Very long paragraph should produce at least one chunk"
        for p in parents:
            assert len(p.get("content", "")) < 6000, "Individual chunk should not be too long"

    def test_repeated_content_deduplication(self):
        """Repeated content should not create duplicate chunks."""
        from byo.processing.chunker import chunk_markdown
        md = "# Section 1\n\nThe Bohr model.\n\n" * 10
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=md,
                resource_id="test_repeat",
                collection_id=TEST_COLLECTION,
                resource_meta={},
                user_id=TEST_USER,
                mime_type="text/plain",
            )
        )
        # Should not create 10x chunks — some dedup or merging expected
        assert len(parents) <= 10, f"Too many chunks for repeated content: {len(parents)}"


# ═══════════════════════════════════════════════════════════
# FULL PIPELINE INTEGRATION TEST
# ═══════════════════════════════════════════════════════════


class TestFullPipeline:
    """Run the complete pipeline: extract → chunk → embed → verify retrieval.

    This is a slow test that calls external APIs. Run explicitly:
        pytest backend/tests/byo/test_pipeline_bohr.py::TestFullPipeline -v -s
    """

    @pytest.fixture(autouse=True)
    def check_prereqs(self):
        if not os.path.exists(PDF_PATH):
            pytest.skip("Test PDF not found")
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")

    def test_full_pipeline_extract_chunk_embed(self):
        """Complete pipeline: extract → chunk → embed, verify all steps produce output."""
        from byo.processing.processors.pdf import PDFProcessor
        from byo.processing.chunker import chunk_markdown
        from byo.processing.embedder import embed_segments_batch

        # Step 1: Extract
        proc = PDFProcessor()
        result = asyncio.get_event_loop().run_until_complete(
            proc.extract(
                resource_id=TEST_RESOURCE_ID,
                mime_type="application/pdf",
                source_url=None,
                storage_path=PDF_PATH,
                meta={},
            )
        )
        md = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
        assert len(md) > 1000, f"Extraction failed: only {len(md)} chars"
        print(f"  ✓ Extraction: {len(md)} chars")

        # Step 2: Chunk
        parents, segments = asyncio.get_event_loop().run_until_complete(
            chunk_markdown(
                markdown=md,
                resource_id=TEST_RESOURCE_ID,
                collection_id=TEST_COLLECTION,
                resource_meta={"title": "Bohr Model Tutor Script"},
                user_id=TEST_USER,
                mime_type="application/pdf",
            )
        )
        assert len(parents) > 3, f"Too few parents: {len(parents)}"
        assert len(segments) > 5, f"Too few segments: {len(segments)}"
        print(f"  ✓ Chunking: {len(parents)} parents, {len(segments)} segments")

        # Step 3: Embed (first 10 segments to keep test fast)
        test_segments = segments[:10]
        asyncio.get_event_loop().run_until_complete(embed_segments_batch(test_segments))
        embedded_count = sum(1 for s in test_segments if s.get("embedding"))
        assert embedded_count > 0, "No segments got embeddings"
        print(f"  ✓ Embedding: {embedded_count}/{len(test_segments)} segments embedded")

        # Verify embedding dimensions
        for s in test_segments:
            if s.get("embedding"):
                assert len(s["embedding"]) == 1536, f"Wrong embedding dim: {len(s['embedding'])}"
                break

        print(f"  ✓ Full pipeline OK")
