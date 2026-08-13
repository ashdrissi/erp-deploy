const fs = require("fs");
const vm = require("vm");

const scriptPath = process.argv[2];
if (!scriptPath) throw new Error("Usage: node quotation_price_scenarios.js <quotation_form_script>");

const script = fs.readFileSync(scriptPath, "utf8");
const formHandlers = {};
const childHandlers = {};
const docs = new Map();
const calls = [];

function jqueryStub() {
    const api = {
        addClass() { return api; },
        after() { return api; },
        append() { return api; },
        attr() { return api; },
        closest() { return api; },
        data() { return undefined; },
        each() { return api; },
        find() { return api; },
        first() { return api; },
        hide() { return api; },
        insertBefore() { return api; },
        length: 0,
        on() { return api; },
        prepend() { return api; },
        remove() { return api; },
        show() { return api; },
        siblings() { return api; },
    };
    return api;
}

const context = {
    console,
    document: { getElementById() { return true; } },
    window: { setTimeout(fn) { fn(); } },
    setTimeout(fn) { fn(); },
    __(value, params) {
        if (!params) return String(value);
        return String(value).replace(/\{(\d+)\}/g, (_, index) => String(params[Number(index)] ?? ""));
    },
    $: jqueryStub,
    frappe: {
        boot: { user: { roles: ["Sales User"] } },
        route_options: {},
        user_roles: ["Sales User"],
        ui: {
            form: {
                on(doctype, handlers) {
                    if (doctype === "Quotation") Object.assign(formHandlers, handlers);
                    if (doctype === "Quotation Item") Object.assign(childHandlers, handlers);
                },
            },
        },
        get_doc(cdt, cdn) {
            return docs.get(cdn);
        },
        get_user_settings(doctype, key) {
            return this.model.user_settings[doctype]?.[key] || {};
        },
        model: {
            user_settings: {},
            clear_table() {},
            set_value(doctype, name, fieldname, value) {
                const row = docs.get(name);
                if (row) row[fieldname] = value;
                calls.push({ doctype, name, fieldname, value });
                return Promise.resolve();
            },
        },
        format(value, df) {
            return Number(value || 0).toFixed(Number(df?.precision ?? 2));
        },
        show_alert() {},
        msgprint(payload) {
            throw new Error(`Unexpected msgprint: ${JSON.stringify(payload)}`);
        },
        utils: {
            escape_html(value) {
                return String(value ?? "");
            },
        },
    },
};

vm.runInNewContext(script, context, { filename: scriptPath });

function assertEqual(label, actual, expected) {
    if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

function assertLinkedValues(label, row, expected) {
    Object.entries(expected).forEach(([fieldname, value]) => {
        assertEqual(`${label} -> ${fieldname}`, row[fieldname], value);
    });
}

function makeRow() {
    const row = {
        doctype: "Quotation Item",
        name: `ROW-${Math.random().toString(36).slice(2)}`,
        item_code: "ITEM-TEST",
        qty: 2,
        price_list_rate: 100,
        rate: 100,
        amount: 200,
        discount_percentage: 0,
        source_price_list_sell_rate: 100,
        source_max_discount_percent: 25,
        source_discount_percent: 0,
        source_discount_amount: 0,
        source_commission_rate: 25,
        source_commission_amount: 0,
        custom_applied_taxes: 40,
        custom_pu_ttc: 120,
        custom_pt_ttc: 240,
    };
    docs.set(row.name, row);
    return row;
}

function makeFrm(row) {
    return {
        __orderlift_applying_quotation_price: false,
        doc: {
            docstatus: 0,
            items: [row],
            taxes: [{ charge_type: "On Net Total", rate: 20 }],
        },
        fields_dict: { items: { grid: {} } },
        refresh_field() {},
        dirty() {},
    };
}

async function runPricingScenarios() {
    const row = makeRow();
    const frm = makeFrm(row);
    const cdt = "Quotation Item";
    const cdn = row.name;

    row.rate = 120;
    await childHandlers.rate(frm, cdt, cdn);
    assertLinkedValues("PU HT above list", row, {
        qty: 2,
        price_list_rate: 100,
        source_price_list_sell_rate: 100,
        rate: 120,
        amount: 240,
        discount_percentage: 0,
        source_max_discount_percent: 25,
        source_discount_percent: 0,
        source_discount_amount: 0,
        source_commission_rate: 25,
        source_commission_amount: 15,
        custom_applied_taxes: 48,
        custom_pu_ttc: 144,
        custom_pt_ttc: 288,
    });

    row.source_discount_percent = 25;
    await childHandlers.source_discount_percent(frm, cdt, cdn);
    assertLinkedValues("Remise %", row, {
        qty: 2,
        price_list_rate: 100,
        source_price_list_sell_rate: 100,
        rate: 75,
        amount: 150,
        discount_percentage: 25,
        source_max_discount_percent: 25,
        source_discount_percent: 25,
        source_discount_amount: 25,
        source_commission_rate: 25,
        source_commission_amount: 0,
        custom_applied_taxes: 30,
        custom_pu_ttc: 90,
        custom_pt_ttc: 180,
    });

    row.source_discount_amount = 12.5;
    await childHandlers.source_discount_amount(frm, cdt, cdn);
    assertLinkedValues("Remise PU HT", row, {
        qty: 2,
        price_list_rate: 100,
        source_price_list_sell_rate: 100,
        rate: 87.5,
        amount: 175,
        discount_percentage: 12.5,
        source_max_discount_percent: 25,
        source_discount_percent: 12.5,
        source_discount_amount: 12.5,
        source_commission_rate: 25,
        source_commission_amount: 5.46875,
        custom_applied_taxes: 35,
        custom_pu_ttc: 105,
        custom_pt_ttc: 210,
    });

    row.qty = 3;
    childHandlers.qty(frm, cdt, cdn);
    assertLinkedValues("Qty", row, {
        qty: 3,
        price_list_rate: 100,
        source_price_list_sell_rate: 100,
        rate: 87.5,
        amount: 262.5,
        discount_percentage: 12.5,
        source_max_discount_percent: 25,
        source_discount_percent: 12.5,
        source_discount_amount: 12.5,
        source_commission_rate: 25,
        source_commission_amount: 8.203125,
        custom_applied_taxes: 52.5,
        custom_pu_ttc: 105,
        custom_pt_ttc: 315,
    });
    assertEqual("PU TTC has no price-input handler", typeof childHandlers.custom_pu_ttc, "undefined");
    assertEqual("legacy gross snapshot absent", typeof row.source_gross_sell_rate, "undefined");
    assertEqual("legacy discounted snapshot absent", typeof row.source_discounted_sell_rate, "undefined");
    return row;
}

function makeGridFrm() {
    const fieldnames = [
        "item_code",
        "qty",
        "source_price_list_sell_rate",
        "rate",
        "source_max_discount_percent",
        "source_discount_percent",
        "source_discount_amount",
        "amount",
        "source_commission_rate",
        "source_commission_amount",
        "custom_applied_taxes",
        "custom_pu_ttc",
        "custom_pt_ttc",
        "source_target_margin_percent",
        "source_margin_percent",
        "source_margin_basis",
        "source_base_buy_rate",
        "source_landed_cost",
    ];
    const docfields = fieldnames.map((fieldname) => ({ fieldname }));
    const grid = {
        doctype: "Quotation Item",
        df: {},
        docfields,
        grid_rows: [],
        customButtons: [],
        wrapper: {},
        add_custom_button(label, callback, position) {
            this.customButtons.push({ label, callback, position });
            return jqueryStub();
        },
        refresh() {},
        get_field(fieldname) {
            return docfields.find((df) => df.fieldname === fieldname);
        },
        update_docfield_property(fieldname, property, value) {
            const df = this.get_field(fieldname);
            if (df) df[property] = value;
        },
    };
    return {
        doctype: "Quotation",
        doc: { docstatus: 0, items: [], taxes: [] },
        fields_dict: {
            items: { grid },
            opportunity: { wrapper: {} },
            source_pricing_sheet: { wrapper: {} },
        },
        add_custom_button() {},
        refresh_field() {},
        set_df_property() {},
        set_query() {},
        toggle_display() {},
        toggle_enable() {},
        get_field(fieldname) { return this.fields_dict[fieldname]; },
    };
}

async function runDraftTTCRecalculateScenario() {
    const row = makeRow();
    row.custom_applied_taxes = 0;
    row.custom_pu_ttc = 0;
    row.custom_pt_ttc = 0;

    const frm = makeGridFrm();
    frm.doc.items = [row];
    frm.doc.taxes = [];
    frm.doc.taxes_and_charges = "VAT 20%";
    let nativeCalculationCalls = 0;
    frm.cscript = {
        async calculate_taxes_and_totals() {
            nativeCalculationCalls += 1;
            frm.doc.taxes = [{ charge_type: "On Net Total", rate: 20 }];
        },
    };

    formHandlers.refresh(frm);
    await Promise.resolve();
    if (frm.__orderlift_ttc_recalculation_queue) {
        await frm.__orderlift_ttc_recalculation_queue;
    }
    assertEqual("automatic Draft TTC sync calls native totals", nativeCalculationCalls > 0, true);
    assertEqual("automatic Draft TTC sync -> applied tax", row.custom_applied_taxes, 40);
    assertEqual("automatic Draft TTC sync -> PU TTC", row.custom_pu_ttc, 120);
    assertEqual("automatic Draft TTC sync -> PT TTC", row.custom_pt_ttc, 240);

    row.custom_applied_taxes = 0;
    row.custom_pu_ttc = 0;
    row.custom_pt_ttc = 0;
    const button = frm.fields_dict.items.grid.customButtons.find(
        (entry) => entry.label === "Recalculate TTC"
    );
    if (!button) throw new Error("Draft Quotation item grid is missing Recalculate TTC button");
    assertEqual("Recalculate TTC button is beside row actions", button.position, undefined);

    await button.callback();
    assertEqual("manual TTC action calls native totals", nativeCalculationCalls > 0, true);
    assertEqual("manual TTC action -> applied tax", row.custom_applied_taxes, 40);
    assertEqual("manual TTC action -> PU TTC", row.custom_pu_ttc, 120);
    assertEqual("manual TTC action -> PT TTC", row.custom_pt_ttc, 240);
}

function runLinePrecisionScenario() {
    const row = makeRow();
    row.qty = 3;
    row.rate = 100.123456789;

    const frm = makeFrm(row);
    childHandlers.qty(frm, "Quotation Item", row.name);

    const expectedAmount = row.rate * row.qty;
    const expectedPuTtc = row.rate * 1.2;
    const expectedPtTtc = expectedAmount * 1.2;
    assertEqual("amount retains canonical precision", row.amount, expectedAmount);
    assertEqual("PU TTC is derived without hard rounding", row.custom_pu_ttc, expectedPuTtc);
    assertEqual("PT TTC is derived without hard rounding", row.custom_pt_ttc, expectedPtTtc);
    assertEqual("tax is derived without hard rounding", row.custom_applied_taxes, expectedPtTtc - expectedAmount);
}

function runGridScenario() {
    const frm = makeGridFrm();
    formHandlers.refresh(frm);
    const grid = frm.fields_dict.items.grid;
    const visible = grid.docfields
        .filter((column) => column.in_list_view && !column.hidden)
        .map((column) => column.fieldname);
    assertEqual("restricted user margin percent excluded", visible.includes("source_margin_percent"), false);
    assertEqual("restricted user margin basis excluded", visible.includes("source_margin_basis"), false);
    assertEqual("margin percent hidden", grid.get_field("source_margin_percent").hidden, 1);
    assertEqual("margin basis hidden", grid.get_field("source_margin_basis").hidden, 1);
    assertEqual("native PU HT editable", grid.get_field("rate").read_only, 0);
    assertEqual("native PT HT read-only", grid.get_field("amount").read_only, 1);
    assertEqual("derived PU TTC read-only", grid.get_field("custom_pu_ttc").read_only, 1);
    assertEqual("derived PU TTC precision", grid.get_field("custom_pu_ttc").precision, "9");
    assertEqual("PU HT static display uses two decimals", grid.get_field("rate").formatter(12.3456789), "12.35");
    assertEqual("quantity static display uses two decimals", grid.get_field("qty").formatter(12.3456789), "12.35");
    assertEqual("max discount static display uses two decimals", grid.get_field("source_max_discount_percent").formatter(0), "0.00%");

    const orderedVisible = grid.docfields
        .filter((column) => column.in_list_view && Number(column.columns || 0) > 0)
        .map((column) => column.fieldname);
    const expectedOrder = [
        "item_code",
        "qty",
        "source_price_list_sell_rate",
        "rate",
        "source_max_discount_percent",
        "source_discount_percent",
        "source_discount_amount",
        "amount",
        "custom_pu_ttc",
        "custom_pt_ttc",
        "source_commission_rate",
        "source_commission_amount",
    ];
    expectedOrder.forEach((fieldname) => assertEqual(`${fieldname} visible`, orderedVisible.includes(fieldname), true));
    assertEqual("derived PT TTC read-only", grid.get_field("custom_pt_ttc").read_only, 1);
    assertEqual("derived PT TTC precision", grid.get_field("custom_pt_ttc").precision, "9");
    [
        "source_price_list_sell_rate",
        "rate",
        "source_discount_amount",
        "amount",
        "custom_applied_taxes",
    ].forEach((fieldname) => {
        assertEqual(`${fieldname} canonical precision`, grid.get_field(fieldname).precision, "9");
    });
}

function runConfiguredMarginScenario() {
    context.frappe.user_roles = ["Orderlift Admin"];
    context.frappe.boot.user.roles = ["Orderlift Admin"];
    context.frappe.boot.orderlift_capabilities = { privileged_pricing: true };
    const savedColumns = [
        { fieldname: "item_code", columns: 2, sticky: 0 },
        { fieldname: "source_margin_percent", columns: 1, sticky: 0 },
    ];
    context.frappe.model.user_settings.Quotation = {
        GridView: { "Quotation Item": savedColumns.map((column) => ({ ...column })) },
    };

    const frm = makeGridFrm();
    formHandlers.refresh(frm);
    const persisted = context.frappe.model.user_settings.Quotation.GridView["Quotation Item"];
    assertEqual("configured columns preserved", JSON.stringify(persisted), JSON.stringify(savedColumns));
    assertEqual("authorized margin visible", frm.fields_dict.items.grid.get_field("source_margin_percent").hidden, 0);
    assertEqual("margin percent uses two decimals", frm.fields_dict.items.grid.get_field("source_margin_percent").formatter(12.3456789), "12.35%");
    assertEqual("landed cost uses two decimals", frm.fields_dict.items.grid.get_field("source_landed_cost").formatter(12.3456789), "12.35");
}

async function runSubmittedLockScenario() {
    const row = makeRow();
    const frm = makeGridFrm();
    frm.doc.docstatus = 1;
    frm.doc.items = [row];
    formHandlers.refresh(frm);

    const grid = frm.fields_dict.items.grid;
    assertEqual("submitted PU HT locked", grid.get_field("rate").read_only, 1);
    assertEqual("submitted discount percent locked", grid.get_field("source_discount_percent").read_only, 1);
    assertEqual("submitted discount amount locked", grid.get_field("source_discount_amount").read_only, 1);
    assertEqual("submitted quantity locked", grid.get_field("qty").read_only, 1);
    assertEqual("submitted inline editing disabled", grid.df.in_place_edit, 0);

    const callsBefore = calls.length;
    row.source_discount_percent = 5;
    await childHandlers.source_discount_percent(frm, "Quotation Item", row.name);
    assertEqual("submitted discount handler does not rewrite rate", row.rate, 100);
    assertEqual("submitted discount handler does not rewrite amount", row.amount, 200);
    assertEqual("submitted discount handler makes no model writes", calls.length, callsBefore);
}

async function main() {
    const finalRow = await runPricingScenarios();
    runLinePrecisionScenario();
    runGridScenario();
    runConfiguredMarginScenario();
    await runDraftTTCRecalculateScenario();
    await runSubmittedLockScenario();

    console.log(JSON.stringify({
        ok: true,
        finalRow: {
            qty: finalRow.qty,
            pu_list_ht: finalRow.source_price_list_sell_rate,
            pu_ht: finalRow.rate,
            remise_percent: finalRow.source_discount_percent,
            remise_pu_ht: finalRow.source_discount_amount,
            pt_ht: finalRow.amount,
            pu_ttc: finalRow.custom_pu_ttc,
            pt_ttc: finalRow.custom_pt_ttc,
        },
        submitted_locked: true,
        setValueCalls: calls.length,
    }, null, 2));
}

main().catch((error) => {
    console.error(error && error.stack ? error.stack : error);
    process.exitCode = 1;
});
