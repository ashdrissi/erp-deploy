import frappe
from frappe import _


RETIRED_MESSAGE = "Pricing Simulator has been retired. Use Pricing Sheet Builder instead."


def deny_pricing_simulator_access():
    frappe.throw(_(RETIRED_MESSAGE), frappe.PermissionError)
