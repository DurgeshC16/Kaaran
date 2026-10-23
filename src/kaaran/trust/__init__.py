"""Data trust checks (no LLM): flat attendance, jumps, missing data, duplicates; see docs/CONFIDENCE_RULES.md."""

from .run import TrustResult, as_pack, run_trust

__all__ = ["TrustResult", "as_pack", "run_trust"]
