# Campaign Workflows

Orderlift campaigns use one selected campaign type per campaign. `Campaign Type` is separate from ERPNext's channel-only `Default Channel`, which remains limited to blank, `Email`, `WhatsApp`, and `Call`.

- `Email`: compose subject/body and send or schedule through ERPNext/Frappe Email Queue.
- `WhatsApp`: use manual click-to-chat links, Twilio templates, or a custom webhook such as Make.com.
- `Call`: store the call script and mark targets contacted from Campaign Manager.
- `Visit`: store visit subject/agenda, set target visit dates, and create/update visit ToDos.
- `Other`: store notes for manual non-standard outreach and mark targets completed.

The Campaign Builder Content tab only shows the editor for the selected campaign type. Change the type in the Campaign tab.

Before email or WhatsApp outreach is sent, Campaign Manager now runs a preflight check. It blocks missing/invalid email addresses, missing WhatsApp phone numbers, missing required content, archived/closed/paused campaigns, wrong campaign type, and invalid automated WhatsApp settings. Warnings such as Draft status or unknown template placeholders are shown for confirmation.

Campaign Builder renders email and WhatsApp previews through the backend against a selected target, so placeholders like `{{ first_name }}`, `{{ company }}`, and `{{ selected_articles }}` can be reviewed before saving or sending.

For automated WhatsApp, configure `Orderlift WhatsApp Settings` after migration. Supported providers are `Twilio` and `Custom Webhook`.

After deploying schema changes, run `bench --site <site> migrate`, clear cache, and reload Desk.
