"""Step 2b (optional): repair the record with small deterministic rules, between the LLM and the scoring."""

from .base import Change, RepairResult, RepairRule
from .factory import build_repairer, register_repair_rule
from .repairer import Repairer

__all__ = [
    "Change",
    "RepairResult",
    "RepairRule",
    "Repairer",
    "build_repairer",
    "register_repair_rule",
]
