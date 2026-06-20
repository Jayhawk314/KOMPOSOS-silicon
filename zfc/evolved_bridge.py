# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Evolved ZFC Verification — ZFC checks against discovered principles, not just raw facts.

Wires AxiomMiner into the default verification path so that:
1. System 3 episodes are continuously mined for emergent axioms
2. Discovered axioms are injected into the ZFC Theory
3. Future verifications use the evolved theory, not just raw facts

This closes the loop:
  Episodes → AxiomMiner → discovered axioms → evolved Theory → ZFC verification
  (raw facts)                                         (principles)

The system literally builds its own mathematical foundation from experience.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.category import Category

from .store_adapter import StoreAdapter
from .bridge import DualEngineBridge, DualResult
from .meta_kan import System3Oracle, DeltaType
from .axiom_miner import AxiomMiner
from .logic import Theory

logger = logging.getLogger(__name__)


class EvolvedDualEngineBridge:
    """
    Dual Engine Bridge with evolved axioms.

    Wraps the standard DualEngineBridge and injects AxiomMiner's
    discovered axioms into the ZFC Theory used for verification.

    Usage:
        bridge = EvolvedDualEngineBridge(
            category=cat,
            system3_oracle=system3,
            auto_mine=True,  # auto-mine after each query
            min_support=10,  # min episodes to promote an axiom
        )

        # Normal use — but ZFC now checks against evolved axioms
        result = bridge.query("Python", "ML", "supports")
    """

    def __init__(
        self,
        category: "Category",
        system3_oracle: System3Oracle = None,
        auto_mine: bool = True,
        min_support: int = 5,
        min_agree_rate: float = 0.75,
        min_confidence: float = 0.4,
    ):
        """
        Args:
            category: The Category for both CAT and ZFC verification.
            system3_oracle: System 3 oracle with episode history.
            auto_mine: If True, mine axioms on every query.
            min_support: Min episodes to promote a pattern to axiom.
            min_agree_rate: Min agreement rate for axiom promotion.
            min_confidence: Min avg confidence for axiom promotion.
        """
        self.category = category
        self.system3 = system3_oracle
        self.auto_mine = auto_mine
        self.min_support = min_support
        self.min_agree_rate = min_agree_rate
        self.min_confidence = min_confidence

        # Build the underlying DualEngineBridge
        adapter = StoreAdapter(category)
        self.base_bridge = DualEngineBridge(adapter, category=category)

        # Axiom miner and evolved theory
        self.axiom_miner = AxiomMiner(system3_oracle, category=category) if system3_oracle else None
        self._evolved_theory: Optional[Theory] = None
        self._axiom_injection_count = 0
        self._last_episode_count = 0

        # If system3 has episodes, mine immediately
        if self.axiom_miner and auto_mine:
            self._mine_and_inject()

    def _mine_and_inject(self) -> bool:
        """
        Mine System 3 episodes for emergent axioms and inject into ZFC Theory.

        Returns:
            True if new axioms were discovered and injected.
        """
        if not self.axiom_miner or not self.system3:
            return False

        # Check if new episodes have accumulated
        total_episodes = (
            len(self.system3.history._resolved) +
            len(self.system3.history._unresolved)
        )
        if total_episodes <= self._last_episode_count:
            return False  # No new episodes

        # Mine axioms
        discovered = self.axiom_miner.discover_axioms(
            min_support=self.min_support,
            min_agree_rate=self.min_agree_rate,
            min_confidence=self.min_confidence,
        )

        if discovered.axioms:
            # Build evolved theory: original axioms + discovered axioms
            adapter = StoreAdapter(self.category)
            base_theory = adapter.to_theory()

            # Combine base axioms with discovered formulas
            all_axioms = list(base_theory.axioms) + discovered.formulas
            self._evolved_theory = Theory(
                name=f"{base_theory.name}+evolved({len(discovered.axioms)})",
                axioms=all_axioms,
            )
            self._axiom_injection_count += 1
            self._last_episode_count = total_episodes

            logger.info(
                f"[EvolvedBridge] Injected {len(discovered.axioms)} evolved axioms "
                f"(total injections: {self._axiom_injection_count}, "
                f"episodes: {total_episodes})"
            )
            return True

        self._last_episode_count = total_episodes
        return False

    def query(
        self,
        source: str,
        target: str,
        relation: str,
        domain: str = "",
        record: bool = True,
    ) -> DualResult:
        """
        Run the dual engine with evolved axioms.

        If auto_mine is enabled, mines axioms before each query.
        ZFC verification uses the evolved theory (raw facts + discovered principles).

        Returns:
            DualResult with evolved axiom metadata.
        """
        # Mine axioms if new episodes available
        if self.auto_mine:
            self._mine_and_inject()

        # Run the base dual engine query
        result = self.base_bridge.query(
            source, target, relation, domain=domain, record=record
        )

        # Add evolved axiom metadata to the result
        if self._evolved_theory:
            result.evidence = getattr(result, 'evidence', {}) or {}
            result.evidence["evolved_axioms"] = {
                "count": len(self._evolved_theory.axioms),
                "injection_count": self._axiom_injection_count,
                "theory_name": self._evolved_theory.name,
            }

        return result

    def verify_with_evolved_axioms(
        self,
        formula,
        domain: str = "",
    ) -> Dict[str, Any]:
        """
        Verify a formula against the evolved theory (not just raw facts).

        Args:
            formula: ZFC Formula to verify.
            domain: Domain label for episode recording.

        Returns:
            Dict with satisfaction result, theory used, and axiom count.
        """
        if self.auto_mine:
            self._mine_and_inject()

        theory = self._evolved_theory or StoreAdapter(self.category).to_theory()

        # Check entailment
        is_entailed = theory.entails(formula)
        num_axioms = len(theory.axioms)

        return {
            "entailed": is_entailed,
            "theory_name": theory.name,
            "num_axioms": num_axioms,
            "evolved_axioms": num_axioms - len(StoreAdapter(self.category).to_theory().axioms),
        }

    def get_evolved_axioms_report(self) -> str:
        """
        Get a report on evolved axioms discovered from episode history.

        Returns:
            Human-readable report on discovered axioms.
        """
        if self.axiom_miner:
            return self.axiom_miner.report()
        return "No axiom miner configured (no System 3 oracle provided)."

    def system3_report(self) -> str:
        """Delegate to base bridge's System 3 report."""
        return self.base_bridge.system3_report()

    def resolve(self, episode_id: str, resolution, notes: str = "") -> None:
        """Delegate to base bridge's resolve."""
        self.base_bridge.resolve(episode_id, resolution, notes)

    def should_run_both(self, source, target, relation, domain=""):
        """Delegate to base bridge."""
        return self.base_bridge.should_run_both(source, target, relation, domain)

    def predict(self, source, target, relation, domain=""):
        """Delegate to base bridge."""
        return self.base_bridge.predict(source, target, relation, domain)
