# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This bridge plugin is dual-licensed (Apache-2.0 OR KOMPOSOS-IV-Commercial).
# It integrates with Orion Core, which is separately licensed under MIT.
# Orion Core © Borkwork (https://github.com/borkwork/orion-framework)

"""
Session Manager Plugin for Orion

Manages per-user COG sessions with persistent memory via KOMPOSOS-IV Categories.

This is a KOMPOSOS-IV plugin that integrates with Orion Core (MIT licensed).
"""

from __future__ import annotations

import logging
import sys
import os

# Add orion-main to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'orion-main', 'src'))

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import from Orion (MIT licensed by Borkwork)
from orion_core import Plugin
from orion_core.plugin import on, hook

# Import from KOMPOSOS-IV
from core.category import Category
from cog.session import CogSession
from cog.engine import CogEngine


class SessionManagerPlugin(Plugin):
    """
    Manage per-user COG sessions with persistent memory.

    Capabilities provided:
    - session_manager: Hot-load and manage user sessions

    Events consumed:
    - user.login: Load user session
    - user.logout: Save and unload user session

    Events published:
    - session.loaded: User session loaded
    - session.saved: User session saved
    """

    def __init__(
        self,
        core,
        *,
        sessions_dir: str = "sessions",
    ):
        """Initialize session manager.

        Args:
            core: Orion Core instance
            sessions_dir: Directory for per-user session databases
        """
        super().__init__(
            core,
            name="session_manager",
            version="0.1.0",
            description="Per-user COG session management",
            provides={"session_manager"},
            events_published={"session.loaded", "session.saved"},
        )

        self.sessions_dir = sessions_dir
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

        # Ensure sessions directory exists
        os.makedirs(sessions_dir, exist_ok=True)

    async def on_start(self):
        """Plugin startup."""
        logger.info(
            f"Session Manager started. Sessions dir: {self.sessions_dir}"
        )

    async def on_stop(self):
        """Plugin shutdown - save all active sessions."""
        for user_id in list(self.active_sessions.keys()):
            await self.save_session(user_id)

        logger.info(
            f"Session Manager stopped. Saved {len(self.active_sessions)} sessions."
        )

    # ========================================================================
    # Public API Methods
    # ========================================================================

    async def get_or_create_session(
        self, user_id: str
    ) -> Dict[str, Any]:
        """
        Get or create a user session.

        Args:
            user_id: User identifier

        Returns:
            Session dict with category and cog_engine
        """
        if user_id in self.active_sessions:
            return self.active_sessions[user_id]

        # Create new session
        db_path = os.path.join(self.sessions_dir, f"{user_id}.db")

        # Create persistent Category
        category = Category(db_path=db_path)

        # Create COG session on that Category
        cog_session = CogSession(session_id=user_id)
        cog_session.category = category
        cog_engine = CogEngine(cog_session)

        session = {
            "user_id": user_id,
            "category": category,
            "cog_session": cog_session,
            "cog_engine": cog_engine,
            "db_path": db_path,
        }

        self.active_sessions[user_id] = session

        await self.emit("session.loaded", {"user_id": user_id})
        return session

    async def save_session(self, user_id: str) -> bool:
        """
        Save a user session.

        Args:
            user_id: User identifier

        Returns:
            True if saved successfully
        """
        if user_id not in self.active_sessions:
            return False

        session = self.active_sessions[user_id]

        # Get summary before saving
        summary = session["cog_session"].get_summary()

        await self.emit(
            "session.saved",
            {
                "user_id": user_id,
                "summary": summary,
            },
        )

        return True

    async def unload_session(self, user_id: str) -> bool:
        """
        Save and unload a user session.

        Args:
            user_id: User identifier

        Returns:
            True if unloaded successfully
        """
        if user_id not in self.active_sessions:
            return False

        await self.save_session(user_id)
        del self.active_sessions[user_id]

        return True

    async def list_active_sessions(self) -> List[str]:
        """Get list of active session user IDs."""
        return list(self.active_sessions.keys())

    async def get_session_summary(self, user_id: str) -> Optional[Dict]:
        """Get summary for a user session."""
        if user_id not in self.active_sessions:
            return None

        session = self.active_sessions[user_id]
        return session["cog_session"].get_summary()

    # ========================================================================
    # Event Handlers
    # ========================================================================

    @on("user.login")
    async def on_user_login(self, event):
        """Handle user login - load session."""
        user_id = event.data["user_id"]
        session = await self.get_or_create_session(user_id)
        return session

    @on("user.logout")
    async def on_user_logout(self, event):
        """Handle user logout - save and unload session."""
        user_id = event.data["user_id"]
        return await self.unload_session(user_id)

    @on("session.query")
    async def on_session_query(self, event):
        """Handle session query - get session info."""
        user_id = event.data["user_id"]
        return await self.get_session_summary(user_id)

    # ========================================================================
    # Hooks
    # ========================================================================

    @hook("session.access", priority=10)
    async def access_session_hook(self, user_id):
        """
        Hook for session access pipeline.

        Returns the user's session.
        """
        return await self.get_or_create_session(user_id)
