# Purchase Agent Rules

Purchase Agent Rules control Buying Price List access for purchasing workflows.
They are separate from Sales Agent Rules and do not contain sales commissions,
selling lists, payment terms, discounts, benchmark policies, customs policies, or
margin policies.

## Access Model

Buying Price List access is capability and policy driven:

```
privileged_pricing capability
  -> all active Buying Price Lists in the active company

purchasing_access capability without privileged_pricing
  -> only active lists in an enabled Purchase Agent Rule for the current User and company

no matching Purchase Agent Rule
  -> no Buying Price Lists
```

The policy is linked directly to a User and Company. It does not use Sales Person,
Project, Business Type, Cost Center, Customer, or Sales Agent Rules.

## Policy Setup

Purchase Agent Rules contains:

- Purchase User: the System User receiving the allowance.
- Company: the company where the allowance applies.
- Enabled: disables the whole rule without deletion.
- Allowed Buying Price Lists: active Buying lists only, with an optional default and priority.

Only one enabled rule may exist for a User and Company. A rule can contain several
active Buying Price Lists, but only one active row can be the default.

## Management Capability

The `purchase_agent_rules_management` capability controls who can open and manage
Purchase Agent Rules. It is assigned through Role Capabilities, not hardcoded role
names. The same capability gates the Main Dashboard menu entry.

The `privileged_pricing` capability bypasses the allowance when selecting or loading
Buying Price Lists, but does not itself grant policy-management access.

## Purchase Documents

Purchase Order source-list selection, supplier Buying Price List suggestions, client
queries, and server-side save validation all resolve through the same policy. A list
manually injected into a PO is rejected if it is not allowed for the current user and
active company.
