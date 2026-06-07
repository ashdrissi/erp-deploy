"""Training Center page server endpoints.

The page itself uses methods from `orderlift.orderlift_hr.api.training`; this
module exists so the page folder follows the project's standard layout (mirrors
hr_dashboard.py). Keep server logic in `api.training` so it can be reused.
"""

from __future__ import annotations

import frappe  # noqa: F401
