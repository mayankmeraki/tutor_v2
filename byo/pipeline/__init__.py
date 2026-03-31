"""BYO processing pipeline.

Extract → Chunk → Classify → Embed → Store

Each step is independent and can be retried.
The orchestrator manages the pipeline for each resource.
"""
