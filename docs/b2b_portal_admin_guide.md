# B2B Portal Admin Guide

## Purpose

The Orderlift B2B Portal is an invite-only customer portal where approved customer users can:
- log in
- see only the products allowed for their customer group
- see prices resolved from the customer group's portal price list
- submit quotation requests for internal review

## Core Objects

### 1. Portal Customer Group Policy

One policy per `Customer Group`.

Main fields:
- `Enabled`
- `Portal Price List`
- `Currency`
- `Quote Request Allowed`
- `Request Approval Required`
- `Allowed Products`

Admin helpers available on the policy form:
- live product summary in the dashboard headline
- missing-price warning against the selected portal price list
- `Preview Portal Catalog`
- `Readiness Check`
- `Bulk Add Products`
- `Remove Disabled Rows`

### 2. Allowed Products

Stored as child rows inside the customer-group policy.

Each row can point to either:
- one `Item`
- or one `Product Bundle`

Each row also supports:
- `Featured`
- `Allow Quote`
- `Sort Order`
- `Portal Title`
- `Short Description`

## Recommended Setup Order

1. Create or confirm the target `Customer Group`
2. Create one `Portal Customer Group Policy`
3. Set the group's `Portal Price List`
4. Add allowed products in `Allowed Products`
5. Invite portal user and link them to the customer
6. Test login on `/b2b-portal`

## Bulk Product Assignment

On `Portal Customer Group Policy`, use `Allowed Products -> Bulk Add Products` to add many items at once.

Current bulk-add filters:
- `item_group`
- `brand`

Bundle bulk-add is also available using the same filters. Bundle matching is resolved through the bundle parent item.

The bulk add action will:
- add only active items
- avoid duplicates already present in the policy
- copy item name into `Portal Title`
- copy item description into `Short Description`
- assign sequential `Sort Order`

## Readiness Check

Use `Allowed Products -> Readiness Check` on the policy form to validate:
- policy enabled state
- portal price list selected
- allowed products exist
- allowed items/bundles resolve to actual items
- each allowed item has a valid price in the selected portal price list

## Invite a Portal User

Use one of these paths:
- customer form button: `B2B Portal -> Invite Portal User`
- server method: `orderlift.orderlift_client_portal.api.invite_portal_user`

The invite helper will:
- create or reuse the `User`
- assign role `B2B Portal Client`
- force `Website User` for portal-only users
- create or reuse the `Contact`
- link contact to customer
- set `Customer.customer_primary_contact` when missing
- link customer to portal users

## Portal-Only Behavior

Portal-only users:
- are redirected to `/b2b-portal` after login
- are redirected away from `/app` and `/desk`
- should not have internal roles like `System Manager`, `Sales Manager`, or `Orderlift Admin`

## Troubleshooting

### Portal shows empty catalog

Check:
- user is linked to the right customer
- customer has a customer group
- customer group has an enabled policy
- policy has enabled allowed products
- allowed products have valid prices in the portal price list

### User still lands in Desk

Check:
- `User Type = Website User`
- role includes `B2B Portal Client`
- user does not have internal roles

### Request submitted but no quotation created

This is expected until an internal reviewer approves the request and creates the quotation from `Portal Quote Request`.

## Internal Operations

Use the internal dashboard:
- `/app/b2b-portal-dashboard`

Main links:
- `Portal Policies`
- `Portal Quote Requests`
- `Portal Review Board`
- `Customers`
- `Users`

The internal dashboard also shows:
- policy count
- allowed product count
- portal user count
- recent quote requests
- pending review requests
- customer-group coverage
- request status breakdown

## Internal Review Board

Use:
- `/app/portal-review-board`

Purpose:
- open all requests awaiting action in one place
- inspect lines and totals quickly
- approve or reject with comment
- create the real quotation

## Customer Quotation Visibility

Portal customers can:
- see quotation-ready requests in `My Requests`
- open `My Quotations`
- download the quotation PDF once it is created internally

## Customer-Facing Route

- `/b2b-portal`
