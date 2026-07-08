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
        format(value) {
            return String(Number(value || 0));
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

function assertClose(label, actual, expected, tolerance = 0.005) {
    const diff = Math.abs(Number(actual || 0) - expected);
    if (diff > tolerance) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

function assertEqual(label, actual, expected) {
    if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
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
        source_gross_sell_rate: 100,
        source_max_discount_percent: 100,
        source_discount_percent: 0,
        source_discount_amount: 0,
        source_discounted_sell_rate: 100,
        source_commission_rate: 0,
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

function runPricingScenarios() {
    const row = makeRow();
    const frm = makeFrm(row);
    const cdt = "Quotation Item";
    const cdn = row.name;

    row.source_gross_sell_rate = 200;
    childHandlers.source_gross_sell_rate(frm, cdt, cdn);
    assertClose("PU HT edit -> price_list_rate", row.price_list_rate, 200);
    assertClose("PU HT edit -> PU HT net", row.source_discounted_sell_rate, 200);
    assertClose("PU HT edit -> PT HT net", row.amount, 400);
    assertClose("PU HT edit -> PU TTC net", row.custom_pu_ttc, 240);
    assertClose("PU HT edit -> PT TTC net", row.custom_pt_ttc, 480);

    row.source_discount_percent = 5;
    childHandlers.source_discount_percent(frm, cdt, cdn);
    assertClose("Remise % -> Remise HT", row.source_discount_amount, 10);
    assertClose("Remise % -> PU HT net", row.source_discounted_sell_rate, 190);
    assertClose("Remise % -> PT HT net", row.amount, 380);
    assertClose("Remise % -> PU TTC net", row.custom_pu_ttc, 228);
    assertClose("Remise % -> PT TTC net", row.custom_pt_ttc, 456);

    row.source_discount_amount = 50;
    childHandlers.source_discount_amount(frm, cdt, cdn);
    assertClose("Remise HT -> Remise %", row.source_discount_percent, 25);
    assertClose("Remise HT -> PU HT net", row.source_discounted_sell_rate, 150);
    assertClose("Remise HT -> PT HT net", row.amount, 300);
    assertClose("Remise HT -> PU TTC net", row.custom_pu_ttc, 180);
    assertClose("Remise HT -> PT TTC net", row.custom_pt_ttc, 360);

    row.custom_pu_ttc = 210;
    childHandlers.custom_pu_ttc(frm, cdt, cdn);
    assertClose("PU TTC net -> PU HT net", row.source_discounted_sell_rate, 175);
    assertClose("PU TTC net -> Remise HT", row.source_discount_amount, 25);
    assertClose("PU TTC net -> Remise %", row.source_discount_percent, 12.5);
    assertClose("PU TTC net -> PT HT net", row.amount, 350);
    assertClose("PU TTC net -> PT TTC net", row.custom_pt_ttc, 420);

    row.qty = 3;
    childHandlers.qty(frm, cdt, cdn);
    assertClose("Qty -> PU HT net unchanged", row.source_discounted_sell_rate, 175);
    assertClose("Qty -> PT HT net", row.amount, 525);
    assertClose("Qty -> PU TTC net unchanged", row.custom_pu_ttc, 210);
    assertClose("Qty -> PT TTC net", row.custom_pt_ttc, 630);
    return row;
}

function makeGridFrm() {
    const fieldnames = [
        "item_code",
        "qty",
        "source_price_list_sell_rate",
        "source_gross_sell_rate",
        "source_max_discount_percent",
        "source_discount_percent",
        "source_discount_amount",
        "source_discounted_sell_rate",
        "amount",
        "custom_pu_ttc",
        "custom_pt_ttc",
        "source_margin_percent",
        "source_margin_basis",
    ];
    const docfields = fieldnames.map((fieldname) => ({ fieldname }));
    const grid = {
        doctype: "Quotation Item",
        df: {},
        docfields,
        grid_rows: [],
        wrapper: {},
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

function runGridScenario() {
    const frm = makeGridFrm();
    formHandlers.refresh(frm);
    const grid = frm.fields_dict.items.grid;
    const visible = context.frappe.model.user_settings.Quotation.GridView["Quotation Item"].map((column) => column.fieldname);
    assertEqual("restricted user margin percent excluded", visible.includes("source_margin_percent"), false);
    assertEqual("restricted user margin basis excluded", visible.includes("source_margin_basis"), false);
    assertEqual("margin percent hidden", grid.get_field("source_margin_percent").hidden, 1);
    assertEqual("margin basis hidden", grid.get_field("source_margin_basis").hidden, 1);
    assertEqual("PU HT editable", grid.get_field("source_gross_sell_rate").read_only, 0);
    assertEqual("PU HT net read-only", grid.get_field("source_discounted_sell_rate").read_only, 1);
}

const finalRow = runPricingScenarios();
runGridScenario();

console.log(JSON.stringify({
    ok: true,
    finalRow: {
        qty: finalRow.qty,
        pu_ht: finalRow.source_gross_sell_rate,
        remise_percent: finalRow.source_discount_percent,
        remise_ht: finalRow.source_discount_amount,
        pu_ht_net: finalRow.source_discounted_sell_rate,
        pt_ht_net: finalRow.amount,
        pu_ttc_net: finalRow.custom_pu_ttc,
        pt_ttc_net: finalRow.custom_pt_ttc,
    },
    setValueCalls: calls.length,
}, null, 2));
