"""Deterministic ingest: messy raw files -> canonical DuckDB tables with provenance + ingest report."""

from .pipeline import IngestError, IngestResult, ingest, write_duckdb

__all__ = ["IngestError", "IngestResult", "ingest", "write_duckdb"]
