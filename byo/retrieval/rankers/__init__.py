"""Rankers — each returns [(segment_id, parent_chunk_id, score)] given a query.

- dense.py:  Atlas $vectorSearch on segment embeddings
- sparse.py: Atlas $search / BM25 on segment content + topics
- hybrid.py: RRF fusion of dense + sparse with per-modality weights
"""
