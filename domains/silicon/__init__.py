# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
KOMPOSOS-V silicon co-design domain.

The active product is a mature-node reliability co-design layer: find physical-stress
hotspots from real layout data, ground material/geometry fixes in cited facts, and keep
only actions whose tradeoff is proven with a receipt.

Evidence boundaries:
  - `structural_only`: graph/placement signals and counterfactuals.
  - `measured_proxy`: extracted SPEF parasitics and derived current-demand proxies.
  - `validated_hypothesis`: cited material physics plus real layout geometry.
  - `measured`: attested EDA tool output with hashed design context.

Most root math engines are substrate, not product dependencies. See
`docs/SILICON_PRODUCT_BOUNDARY.md` before wiring dormant machinery into reliability.

Start here: docs/HANDOFF.md
Findings: docs/SILICON_FINDINGS.md
Status/log: docs/SILICON_STATUS.md, docs/SESSIONS.md
"""
