"""System prompts for every pipeline phase.

Kept as Python constants (rather than .txt files) so editor tooling shows
references and the prompts are part of the import graph for linting.
"""

from app.ai.prompts.extract import EXTRACT_SYSTEM_PROMPT
from app.ai.prompts.judge import JUDGE_SYSTEM_PROMPT
from app.ai.prompts.research import RESEARCH_SYSTEM_PROMPT
from app.ai.prompts.synth import SYNTH_SYSTEM_PROMPT

__all__ = [
    "EXTRACT_SYSTEM_PROMPT",
    "JUDGE_SYSTEM_PROMPT",
    "RESEARCH_SYSTEM_PROMPT",
    "SYNTH_SYSTEM_PROMPT",
]
