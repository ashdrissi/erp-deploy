import frappe
from frappe.utils import add_days, today, flt


def send_weekly_efficiency_digest():
    """
    Weekly scheduled job. Queries confirmed Forecast Load Plans touched in the last 7 days,
    computes utilization metrics, and emails a digest to all Orderlift Admin users.
    """
    from_date = add_days(today(), -7)

    plans = frappe.get_all(
        "Forecast Load Plan",
        filters={
            "status": ["in", ["Ready", "Loading", "In Transit", "Delivered"]],
            "modified": [">=", from_date],
        },
        fields=[
            "name",
            "plan_label",
            "destination_zone",
            "status",
            "weight_utilization_pct",
            "volume_utilization_pct",
            "limiting_factor",
            "departure_date",
        ],
        order_by="modified desc",
        limit_page_length=0,
    )

    if not plans:
        return  # nothing to report

    total = len(plans)
    ready_count = sum(1 for p in plans if p.status == "Ready")
    loading_count = sum(1 for p in plans if p.status == "Loading")
    transit_count = sum(1 for p in plans if p.status == "In Transit")
    delivered_count = sum(1 for p in plans if p.status == "Delivered")
    avg_weight = round(sum(flt(p.weight_utilization_pct) for p in plans) / total, 1) if total else 0
    avg_volume = round(sum(flt(p.volume_utilization_pct) for p in plans) / total, 1) if total else 0

    # Build HTML rows for each plan
    rows_html = "".join(
        f"""<tr>
            <td>{p.name}</td>
            <td>{p.plan_label or p.name}</td>
            <td>{p.destination_zone or "-"}</td>
            <td>{p.departure_date or "-"}</td>
            <td>{flt(p.weight_utilization_pct):.1f}%</td>
            <td>{flt(p.volume_utilization_pct):.1f}%</td>
            <td>{p.status or "-"}</td>
        </tr>"""
        for p in plans
    )

    html = f"""
    <h3>Weekly Forecast Load Plan Digest</h3>
    <p>Summary for the past 7 days ({from_date} to {today()}):</p>
    <table style="border-collapse:collapse;width:100%;font-size:13px;">
      <tr>
        <td style="padding:8px;background:#f3f7fc;"><b>Total Plans</b></td>
        <td style="padding:8px;">{total}</td>
        <td style="padding:8px;background:#f3f7fc;"><b>Avg Weight Util</b></td>
        <td style="padding:8px;">{avg_weight}%</td>
      </tr>
      <tr>
        <td style="padding:8px;background:#f3f7fc;"><b>Ready / Loading / Transit / Delivered</b></td>
        <td style="padding:8px;">{ready_count} / {loading_count} / {transit_count} / {delivered_count}</td>
        <td style="padding:8px;background:#f3f7fc;"><b>Avg Volume Util</b></td>
        <td style="padding:8px;">{avg_volume}%</td>
      </tr>
    </table>
    <br>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:12px;">
      <thead style="background:#e8f0fb;">
        <tr>
          <th>Plan</th><th>Label</th><th>Zone</th><th>Departure</th>
          <th>Weight %</th><th>Volume %</th><th>Status</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """

    # Send to all Orderlift Admin users
    recipients = frappe.get_all(
        "Has Role",
        filters={"role": "Orderlift Admin", "parenttype": "User"},
        fields=["parent"],
        limit_page_length=0,
    )

    emails = []
    for r in recipients:
        user_email = frappe.db.get_value("User", r.parent, "email")
        if user_email:
            emails.append(user_email)

    if not emails:
        return

    frappe.sendmail(
        recipients=emails,
        subject=f"[Orderlift] Weekly Forecast Plan Digest — {total} plans ({from_date} to {today()})",
        message=html,
        delayed=False,
    )
