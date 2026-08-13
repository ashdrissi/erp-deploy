const assert = require("assert");
const fs = require("fs");
const path = require("path");

const scriptPath = process.argv[2];
const source = fs.readFileSync(scriptPath, "utf8");
const calls = [];

const history = {
    replaceState(...args) {
        calls.push(["replaceState", ...args]);
    },
    pushState(...args) {
        calls.push(["pushState", ...args]);
    },
};

global.window = {
    location: {
        href: "https://erp.example.test/desk/home-page",
        origin: "https://erp.example.test",
        pathname: "/desk/home-page",
        search: "",
        hash: "",
    },
    history,
    addEventListener() {},
};
global.document = { addEventListener() {} };

eval(source);
calls.length = 0;

history.pushState({ route: "same" }, "title");
assert.strictEqual(calls.at(-1).length, 3, "method name plus two native arguments");
assert.strictEqual(calls.at(-1)[0], "pushState");

history.replaceState({}, "title", "/desk/item");
assert.strictEqual(calls.at(-1)[0], "replaceState");
assert.ok(calls.at(-1)[3].includes("sidebar=Main+Dashboard"));
assert.notStrictEqual(calls.at(-1)[3], "/desk/item/undefined");

console.log(JSON.stringify({ ok: true, script: path.basename(scriptPath) }));
