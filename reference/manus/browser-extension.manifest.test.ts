import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const extensionRoot = join(process.cwd(), "browser-extension");
const manifest = JSON.parse(readFileSync(join(extensionRoot, "manifest.json"), "utf8")) as {
  manifest_version: number;
  permissions: string[];
  host_permissions: string[];
  content_scripts: Array<{ matches: string[] }>;
};

describe("Say Less browser companion prototype", () => {
  it("uses Manifest V3 for the supported online meeting web surfaces", () => {
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.host_permissions).toEqual(expect.arrayContaining([
      "https://meet.google.com/*",
      "https://teams.microsoft.com/*",
      "https://app.zoom.us/*",
    ]));
    expect(manifest.content_scripts[0]?.matches).toEqual(manifest.host_permissions);
  });

  it("does not claim browser-tab capture in the prototype", () => {
    expect(manifest.permissions).not.toContain("tabCapture");
    expect(manifest.permissions).not.toContain("desktopCapture");
    const popup = readFileSync(join(extensionRoot, "popup.html"), "utf8");
    const content = readFileSync(join(extensionRoot, "content.js"), "utf8");
    expect(popup).toContain("required participant consent has been recorded");
    expect(content).toContain("not capturing browser-tab audio");
  });
});
