(function () {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", "/assets/orderlift/js/project_sig.js?v=20260425b", false);
    xhr.send(null);
    if (xhr.status >= 200 && xhr.status < 300) {
        (0, eval)(xhr.responseText);
    } else {
        console.error("Unable to load Project SIG asset", xhr.status);
    }
})();
