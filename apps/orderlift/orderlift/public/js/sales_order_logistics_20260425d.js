(function () {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", "/assets/orderlift/js/sales_order_logistics_20260425c.js?v=20260425d", false);
    xhr.send(null);
    if (xhr.status >= 200 && xhr.status < 300) {
        (0, eval)(xhr.responseText);
    } else {
        console.error("Unable to load Sales Order logistics asset", xhr.status);
    }
})();
