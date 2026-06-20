# Orion-KOMPOSOS-COG Bridge Plugins

Integration layer for the three-layer architecture.

## Overview

These bridge plugins connect:
- **Orion Core** (MIT licensed by Borkwork) - Plugin framework
- **KOMPOSOS-IV** (Apache-2.0/Commercial) - Category runtime
- **COG** (Apache-2.0/Commercial) - Cognitive co-processor

## Plugins

### CogReasoningPlugin
Provides COG tiered verification as an Orion capability.

**Capabilities**:
- `reasoning`: Verify claims through categorical verification
- `verification`: Formal proof checking (ZFC + CAT)
- `knowledge_graph`: Query categorical knowledge structure

**Example**:
```python
from bridges import CogReasoningPlugin

# Register plugin
cog_plugin = CogReasoningPlugin(core)
await core.register_plugin(cog_plugin)

# Use via capability
cog = await core.get_capability("reasoning")
result = await cog.verify_claim(
    source="Python",
    target="ML",
    relation="supports"
)
```

### KnowledgeManagerPlugin
Bridges Orion events to KOMPOSOS-IV Category.

**Capabilities**:
- `knowledge_store`: Persistent categorical storage
- `graph_query`: Query categorical graph

**Example**:
```python
from bridges import KnowledgeManagerPlugin

# Register plugin
km_plugin = KnowledgeManagerPlugin(core, db_path="knowledge.db")
await core.register_plugin(km_plugin)

# Use via events
await core.emit("fact.learned", {
    "source": "Python",
    "target": "typing",
    "relation": "supports"
})
```

### SessionManagerPlugin
Manages per-user COG sessions with persistent memory.

**Capabilities**:
- `session_manager`: Hot-load user sessions

**Example**:
```python
from bridges import SessionManagerPlugin

# Register plugin
sm_plugin = SessionManagerPlugin(core, sessions_dir="sessions/")
await core.register_plugin(sm_plugin)

# Use via events
await core.emit("user.login", {"user_id": "alice"})
session = await core.get_capability("session_manager")
alice_session = await session.get_or_create_session("alice")
```

## License

These bridge plugins are dual-licensed:
- Apache License 2.0, OR
- KOMPOSOS-IV Commercial License

They integrate with Orion Core (MIT licensed by Borkwork).

## Attribution

- **Orion Core**: © Borkwork (MIT) - https://github.com/borkwork/orion-framework
- **Bridge Plugins**: © 2024-2026 James Ray Hawkins
