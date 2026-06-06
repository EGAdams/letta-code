"""Scissari executor_run recovery subsystem.

Divide-and-conquer redesign that replaces the blind 14-call retry loop with a
classified, strategy-driven recovery pipeline. See divide_and_conquer_scissari_fix.html
for the full design plan and GoF pattern catalog.

All implementations are stubs that raise NotImplementedError so the unit-test
suite is RED on first run (TDD). Fill one interface at a time until green.
"""

__all__ = [
    "models",
    "interfaces",
    "strategies",
    "classifiers",
    "guard",
    "breaker",
    "service",
]
