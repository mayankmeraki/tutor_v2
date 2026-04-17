"""BYO retrieval — query → ranked chunks with anchors.

Public API: byo.retrieval.service

Talks to: byo.shared (models, storage), MongoDB (byo_segments, byo_chunks), Atlas
Vector Search, Atlas $search, optional Cohere rerank.

Never imports from byo.processing — retrieval and processing are decoupled.
"""
