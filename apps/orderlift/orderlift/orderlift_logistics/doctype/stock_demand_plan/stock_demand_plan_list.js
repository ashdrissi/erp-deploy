frappe.listview_settings["Stock Demand Plan"] = {
    add_fields: ["planning_status"],
    get_indicator(doc) {
        const status = doc.planning_status || "Not Due";
        if (["Fully Reserved", "Covered by Physical Stock"].includes(status)) return [__(status), "green", `planning_status,=,${status}`];
        if (["Covered by Incoming", "Waiting Incoming"].includes(status)) return [__(status), "blue", `planning_status,=,${status}`];
        if (["Incoming Late", "Procurement Late", "Shortage", "Replan Needed"].includes(status)) return [__(status), "red", `planning_status,=,${status}`];
        if (status === "Not Due") return [__(status), "gray", `planning_status,=,${status}`];
        return [__(status), "orange", `planning_status,=,${status}`];
    },
};
