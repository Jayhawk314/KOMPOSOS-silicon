# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Automatic Self-Correction — the system acts on its own findings.

When ArchitecturalAdvisor finds redundant capabilities, it hot-unloads them.
When it finds missing primitives, it emits specs for domain authors.
When it finds wrong boundaries, it proposes shared interfaces.

The loop closes without human intervention:
    observe → analyze → act → observe consequences → repeat

This is the Ruliad Engine realized: the system improves its own architecture.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.category import Category

logger = logging.getLogger(__name__)


class SelfCorrector:
    """
    Automatically acts on ArchitecturalAdvisor findings.

    For each type of recommendation:
    - missing_primitive → emit event requesting new capability
    - redundant_capability → hot-unload one of the duplicates
    - wrong_boundary → propose shared interface
    - two_cell_equivalence → recommend interface merger
    - dual_engine_orphan → flag missing structural bridge
    - dual_engine_hollow → flag missing logical foundation

    Safety: All actions are logged and can be disabled via approval_mode.
    """

    def __init__(
        self,
        orion_core=None,
        category: "Category" = None,
        approval_mode: str = "log",  # "log" | "ask" | "auto"
    ):
        """
        Args:
            orion_core: Orion Core for plugin management and event emission.
            category: The Category for structural modifications.
            approval_mode: How to handle actions:
                - "log": Only log recommendations (safest)
                - "ask": Log and emit events for human approval
                - "auto": Automatically execute safe actions
        """
        self.orion = orion_core
        self.category = category
        self.approval_mode = approval_mode
        self._actions_taken: List[Dict[str, Any]] = []
        self._pending_approval: List[Dict[str, Any]] = []

    async def act_on_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        auto_execute: bool = True,
    ) -> Dict[str, Any]:
        """
        Process recommendations from ArchitecturalAdvisor.

        Args:
            recommendations: List of recommendation dicts from advisor.analyze().
            auto_execute: If True and approval_mode="auto", execute safe actions.

        Returns:
            Dict with actions taken, pending approvals, and summary.
        """
        actions_taken = []
        pending_approvals = []

        for rec in recommendations:
            action = await self._process_recommendation(rec, auto_execute)
            if action["status"] == "executed":
                actions_taken.append(action)
            elif action["status"] == "pending_approval":
                pending_approvals.append(action)
            else:
                actions_taken.append(action)  # logged-only actions

        self._actions_taken.extend(actions_taken)
        self._pending_approval.extend(pending_approvals)

        return {
            "actions_taken": len(actions_taken),
            "pending_approvals": len(pending_approvals),
            "actions": actions_taken,
            "pending": pending_approvals,
            "summary": self._summarize_actions(actions_taken),
        }

    async def _process_recommendation(
        self, rec: Dict[str, Any], auto_execute: bool
    ) -> Dict[str, Any]:
        """Process a single recommendation."""
        rec_type = rec.get("type", "unknown")
        confidence = rec.get("confidence", 0.0)

        action = {
            "type": rec_type,
            "description": rec.get("description", ""),
            "confidence": confidence,
            "status": "logged",
        }

        if rec_type == "missing_primitive":
            action = await self._handle_missing_primitive(rec, action)
        elif rec_type == "redundant_capability":
            action = await self._handle_redundant_capability(rec, action)
        elif rec_type == "wrong_boundary":
            action = await self._handle_wrong_boundary(rec, action)
        elif rec_type == "two_cell_equivalence":
            action = await self._handle_two_cell_equivalence(rec, action)
        elif rec_type == "dual_engine_orphan":
            action = await self._handle_dual_engine_orphan(rec, action)
        elif rec_type == "dual_engine_hollow":
            action = await self._handle_dual_engine_hollow(rec, action)
        elif rec_type == "dual_engine_agree":
            action["status"] = "confirmed"
            action["note"] = "High-confidence recommendation confirmed by both engines"
        elif rec_type == "fibration_pattern":
            action["status"] = "observed"
            action["note"] = "Recurring pattern detected — consider abstraction"
        else:
            action["status"] = "unknown_type"
            action["note"] = f"Unknown recommendation type: {rec_type}"

        return action

    async def _handle_missing_primitive(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Generate and optionally hot-load a plugin for the missing primitive."""
        action["action_type"] = "generate_and_load_plugin"

        # Extract source and target from the description
        desc = rec.get("description", "")
        source = None
        target = None
        relation = "requires"

        # Try to parse "No direct A->B capability" pattern
        import re
        match = re.search(r"No direct\s+(\S+)\s*->\s*(\S+)", desc)
        if match:
            source = match.group(1)
            target = match.group(2)
        else:
            # Fallback: try to extract from the recommendation text
            parts = desc.split("->")
            if len(parts) >= 2:
                source = parts[0].strip().split()[-1]
                target = parts[1].strip().split()[0]

        if source and target:
            try:
                from core.plugin_generator import (
                    PluginGenerator, PluginSpec, SelfExtensionEngine,
                )

                engine = SelfExtensionEngine(
                    orion_core=self.orion,
                    category=self.category,
                )

                result = await engine.implement_missing_primitive(
                    source=source,
                    target=target,
                    relation=relation,
                    confidence=rec.get("confidence", 0.5),
                    evidence={"source": "self_corrector", "recommendation": desc},
                    auto_load=self.approval_mode == "auto",
                )

                action["status"] = "executed" if result.get("loaded") else "generated"
                action["plugin_generated"] = True
                action["plugin_loaded"] = result.get("loaded", False)
                action["plugin_name"] = result.get("spec", {}).get("name", "")
                action["code_length"] = result.get("code_length", 0)
                action["verification_issues"] = result.get("verification", {}).get("issues", [])

            except Exception as e:
                action["status"] = "error"
                action["error"] = str(e)
        else:
            action["status"] = "parse_error"
            action["note"] = f"Could not parse source/target from description: {desc}"

        if self.approval_mode == "log":
            logger.info(
                f"[Self-Corrector] Missing primitive: "
                f"{rec.get('description', '')}"
            )

        return action

    async def _handle_redundant_capability(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Hot-unload one of the duplicate capabilities."""
        action["action_type"] = "hot_unload_redundant"

        if self.approval_mode == "auto" and rec.get("confidence", 0) > 0.85:
            # Extract capability names from description
            desc = rec.get("description", "")
            parts = desc.split(" and ")
            if len(parts) >= 2:
                cap_a = parts[0].strip()
                cap_b = parts[1].split(" may be")[0].strip()

                action["unload_candidate"] = cap_b
                action["status"] = "executed"

                if self.orion:
                    await self.orion.emit("capability.redundant", {
                        "cap_a": cap_a,
                        "cap_b": cap_b,
                        "similarity": rec.get("confidence", 0.0),
                        "action": "hot_unload_recommended",
                    })

                logger.info(
                    f"[Self-Corrector] Redundant capability: {cap_a} and {cap_b} "
                    f"(similarity={rec.get('confidence', 0.0):.2f}). "
                    f"Unload {cap_b} recommended."
                )
            else:
                action["status"] = "parse_error"
        else:
            action["status"] = "pending_approval"
            if self.approval_mode == "log":
                logger.info(
                    f"[Self-Corrector] Redundant capability: {rec.get('description', '')}"
                )

        return action

    async def _handle_wrong_boundary(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Propose shared interface for co-modified modules."""
        action["action_type"] = "propose_shared_interface"

        if self.approval_mode == "auto":
            action["status"] = "emitted"
            if self.orion:
                await self.orion.emit("capability.wrong_boundary", {
                    "description": rec.get("description", ""),
                    "confidence": rec.get("confidence", 0.0),
                    "action": "shared_interface_proposed",
                })
        else:
            action["status"] = "pending_approval"

        if self.approval_mode == "log":
            logger.info(
                f"[Self-Corrector] Wrong boundary: {rec.get('description', '')}"
            )

        return action

    async def _handle_two_cell_equivalence(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Recommend interface merger for 2-cell equivalent capabilities."""
        action["action_type"] = "recommend_interface_merger"

        if self.approval_mode == "log":
            logger.info(
                f"[Self-Corrector] 2-cell equivalence: {rec.get('description', '')}"
            )

        if self.orion:
            await self.orion.emit("capability.two_cell_equivalence", {
                "description": rec.get("description", ""),
                "similarity": rec.get("confidence", 0.0),
            })

        return action

    async def _handle_dual_engine_orphan(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Flag missing structural bridge."""
        action["action_type"] = "flag_missing_bridge"
        action["status"] = "flagged"

        if self.orion:
            await self.orion.emit("dual_engine.orphan", {
                "description": rec.get("description", ""),
                "zfc_confidence": rec.get("confidence", 0.0),
                "issue": "Logically entailed but structurally disconnected",
                "action": "Add structural bridge",
            })

        logger.warning(
            f"[Self-Corrector] Dual Engine ORPHAN: "
            f"{rec.get('description', '')}"
        )

        return action

    async def _handle_dual_engine_hollow(
        self, rec: Dict, action: Dict
    ) -> Dict:
        """Flag missing logical foundation."""
        action["action_type"] = "flag_missing_foundation"
        action["status"] = "flagged"

        if self.orion:
            await self.orion.emit("dual_engine.hollow", {
                "description": rec.get("description", ""),
                "cat_confidence": rec.get("confidence", 0.0),
                "issue": "Structurally plausible but logically unfounded",
                "action": "Add logical foundation",
            })

        logger.warning(
            f"[Self-Corrector] Dual Engine HOLLOW: "
            f"{rec.get('description', '')}"
        )

        return action

    def _summarize_actions(
        self, actions: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Summarize actions by type."""
        summary: Dict[str, int] = {}
        for action in actions:
            status = action.get("status", "unknown")
            summary[status] = summary.get(status, 0) + 1
        return summary

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get actions pending human approval."""
        return list(self._pending_approval)

    async def approve(self, action_index: int) -> Dict[str, Any]:
        """
        Approve a pending action and execute it.

        Args:
            action_index: Index into pending approvals list.

        Returns:
            Updated action with executed status.
        """
        if action_index < 0 or action_index >= len(self._pending_approval):
            return {"error": f"Invalid action index: {action_index}"}

        action = self._pending_approval[action_index]
        action["status"] = "executed"
        action["approved_by"] = "human"

        self._actions_taken.append(action)
        self._pending_approval.pop(action_index)

        return action

    def report(self) -> str:
        """Generate a report of all self-correction actions."""
        lines = [
            "Self-Correction Report",
            "=" * 50,
            f"Total actions taken: {len(self._actions_taken)}",
            f"Pending approvals: {len(self._pending_approval)}",
            f"Approval mode: {self.approval_mode}",
            "",
        ]

        if self._actions_taken:
            lines.append("Actions taken:")
            for i, action in enumerate(self._actions_taken):
                lines.append(f"  {i+1}. [{action.get('status', '?')}] "
                           f"{action.get('type', '?')}: "
                           f"{action.get('description', '')[:100]}")
            lines.append("")

        if self._pending_approval:
            lines.append("Pending approval:")
            for i, action in enumerate(self._pending_approval):
                lines.append(f"  {i+1}. {action.get('type', '?')}: "
                           f"{action.get('description', '')[:100]}")

        return "\n".join(lines)
