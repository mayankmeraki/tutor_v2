"""In-memory BYO content store — for tests only.

No external dependencies. Implements the same BYOContentStore protocol
as QdrantContentStore so tests exercise the same code paths.
"""

from __future__ import annotations

import math
from byo.shared.store import BYOContentStore, ContentHit


class MemoryContentStore:
    """Dict-backed content store. Search uses brute-force cosine."""

    def __init__(self):
        self._points: list[dict] = []  # each has 'vector' + 'payload'

    async def upsert(self, *, resource_id, collection_id, user_id,
                     resource_name, parents, segments) -> tuple[int, int]:
        # Delete existing
        await self.delete_resource(resource_id)

        parent_map = {p["chunk_id"]: p for p in parents}
        count = 0
        for s in segments:
            emb = s.get("embedding")
            if not emb:
                continue
            parent = parent_map.get(s.get("parent_chunk_id", ""), {})
            self._points.append({
                "vector": emb,
                "payload": {
                    "segment_id": s["segment_id"],
                    "chunk_id": s.get("parent_chunk_id", ""),
                    "collection_id": collection_id,
                    "resource_id": resource_id,
                    "resource_name": resource_name,
                    "user_id": user_id,
                    "segment_content": s.get("content", ""),
                    "parent_content": parent.get("content", s.get("content", "")),
                    "anchor_page": (s.get("anchor") or {}).get("page")
                        or (parent.get("anchor") or {}).get("page"),
                    "anchor_section": (s.get("anchor") or {}).get("section", "")
                        or (parent.get("anchor") or {}).get("section", ""),
                    "modality": s.get("modality", ""),
                    "retrieval_mode": s.get("retrieval_mode", ""),
                    "topics": s.get("topics") or parent.get("topics") or [],
                    "labels": parent.get("labels") or [],
                    "index": parent.get("index", s.get("index", 0)),
                },
            })
            count += 1
        return len(parents), count

    async def delete_resource(self, resource_id):
        self._points = [p for p in self._points if p["payload"]["resource_id"] != resource_id]
        return 0

    async def search(self, query_vector, *, user_id, collection_id=None,
                     resource_id=None, modality=None, k=5, min_score=0.35):
        results = []
        q_norm = math.sqrt(sum(x*x for x in query_vector)) or 1e-9
        for p in self._points:
            pl = p["payload"]
            if pl["user_id"] != user_id:
                continue
            if collection_id and pl["collection_id"] != collection_id:
                continue
            if resource_id and pl["resource_id"] != resource_id:
                continue
            dot = sum(a*b for a, b in zip(query_vector, p["vector"]))
            e_norm = math.sqrt(sum(x*x for x in p["vector"])) or 1e-9
            score = dot / (q_norm * e_norm)
            if score < min_score:
                continue
            results.append((score, pl))
        results.sort(key=lambda x: -x[0])

        seen: set[str] = set()
        hits: list[ContentHit] = []
        for score, pl in results[:k * 2]:
            cid = pl["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            hits.append(_pl_to_hit(pl, score))
            if len(hits) >= k:
                break
        return hits

    async def fetch(self, chunk_id, *, user_id):
        for p in self._points:
            pl = p["payload"]
            if pl["chunk_id"] == chunk_id and pl["user_id"] == user_id:
                return _pl_to_hit(pl)
        return None

    async def nearby(self, chunk_id, *, user_id, window=1):
        target = await self.fetch(chunk_id, user_id=user_id)
        if not target:
            return []
        results = []
        seen: set[str] = set()
        for p in self._points:
            pl = p["payload"]
            if pl["resource_id"] != target.resource_id or pl["user_id"] != user_id:
                continue
            if abs(pl["index"] - target.index) > window:
                continue
            cid = pl["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_pl_to_hit(pl))
        results.sort(key=lambda r: r.index)
        return results

    async def list_chunks(self, *, user_id, collection_id=None,
                          resource_id=None, limit=50):
        seen: set[str] = set()
        results: list[ContentHit] = []
        for p in self._points:
            pl = p["payload"]
            if pl["user_id"] != user_id:
                continue
            if collection_id and pl["collection_id"] != collection_id:
                continue
            if resource_id and pl["resource_id"] != resource_id:
                continue
            cid = pl["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_pl_to_hit(pl))
            if len(results) >= limit:
                break
        results.sort(key=lambda r: (r.resource_name, r.index))
        return results

    async def read_resource(self, resource_id, *, user_id,
                            page_start=None, page_end=None):
        seen: set[str] = set()
        results: list[ContentHit] = []
        for p in self._points:
            pl = p["payload"]
            if pl["resource_id"] != resource_id or pl["user_id"] != user_id:
                continue
            page = pl.get("anchor_page")
            if page_start is not None and page is not None and page < page_start:
                continue
            if page_end is not None and page is not None and page > page_end:
                continue
            cid = pl["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_pl_to_hit(pl))
        results.sort(key=lambda r: r.index)
        return results


def _pl_to_hit(pl: dict, score: float = 0.0) -> ContentHit:
    return ContentHit(
        chunk_id=pl.get("chunk_id", ""),
        segment_id=pl.get("segment_id", ""),
        resource_id=pl.get("resource_id", ""),
        resource_name=pl.get("resource_name", ""),
        collection_id=pl.get("collection_id", ""),
        user_id=pl.get("user_id", ""),
        content=pl.get("parent_content", ""),
        segment_content=pl.get("segment_content", ""),
        anchor_page=pl.get("anchor_page"),
        anchor_section=pl.get("anchor_section", ""),
        score=score,
        modality=pl.get("modality", ""),
        retrieval_mode=pl.get("retrieval_mode", ""),
        topics=pl.get("topics") or [],
        labels=pl.get("labels") or [],
        index=pl.get("index", 0),
    )
