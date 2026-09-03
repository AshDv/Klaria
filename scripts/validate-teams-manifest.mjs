import assert from "node:assert/strict";
import fs from "node:fs";

const manifest = JSON.parse(fs.readFileSync(new URL("../teams-app/manifest.json", import.meta.url), "utf8"));
assert.equal(manifest.manifestVersion, "1.19");
assert.match(manifest.id, /^[0-9a-f]{8}-[0-9a-f-]{27}$/i);
assert.equal(manifest.name.short, "Klaria");
assert.ok(manifest.description.short.length <= 80);
assert.ok(manifest.description.full.length <= 4000);
assert.ok(Array.isArray(manifest.staticTabs) && manifest.staticTabs.length > 0);
assert.ok(manifest.staticTabs.every((tab) => tab.scopes?.includes("personal")));
assert.ok(manifest.staticTabs.every((tab) => tab.contentUrl.startsWith("https://")));
assert.ok(manifest.validDomains.every((domain) => !domain.includes("/")));
console.log(`Manifeste Teams valide : ${manifest.staticTabs.length} onglets contrôlés.`);
