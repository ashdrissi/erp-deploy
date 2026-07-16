"""Compatibility entry point for the retired CRM notification placeholder.

The rule and contact-schedule models required by the original design were never
introduced.  Keeping the old job registered made the scheduler look successful
while doing no work, so it is intentionally not listed in ``scheduler_events``.
"""


def run_daily():
    """Report the retired state to any legacy caller without side effects."""
    return {
        "disabled": True,
        "reason": "CRM notification rules and contact schedules are not configured.",
    }
