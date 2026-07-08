frappe.pages["my-todos"].on_page_load = function () {
    route_to_my_open_todos();
};

frappe.pages["my-todos"].on_page_show = function () {
    route_to_my_open_todos();
};

function route_to_my_open_todos() {
    frappe.route_options = {
        status: "Open",
        allocated_to: frappe.session.user,
    };
    frappe.set_route("List", "ToDo", "List");
}
