import { fitTitle, fitDescription } from "../seoText";

describe("fitTitle", () => {
  it("adds the longest brand that fits in 60 characters", () => {
    expect(fitTitle("Cloud Solutions Engineer")).toBe("Cloud Solutions Engineer | Intrinsic Technology");
    expect(fitTitle("A Title of Exactly Forty-Seven Characters Here!")).toBe("A Title of Exactly Forty-Seven Characters Here! | Intrinsic");
    expect(fitTitle("Strengthening Endpoint Security and Patch Compliance")).toBe("Strengthening Endpoint Security and Patch Compliance");
  });
  it("never cuts the title itself", () => {
    const t = "Consolidating Microsoft 365 Domains and SharePoint Without Downtime";
    expect(fitTitle(t)).toBe(t);
  });
});

describe("fitDescription", () => {
  it("leaves short text alone", () => {
    expect(fitDescription("A law firm strengthened endpoint security.")).toBe("A law firm strengthened endpoint security.");
  });
  it("keeps whole sentences when they fill enough of the space", () => {
    const first = "Four email domains and 50+ SharePoint sites were consolidated into a single Microsoft 365 identity with no reported downtime.";
    expect(fitDescription(first + " Permissions and version history were preserved throughout the migration, and staff kept working.")).toBe(first);
  });
  it("otherwise cuts at a whole word, within 155 characters", () => {
    const long = "A precast concrete manufacturer modernized its production management system on Microsoft Azure while retaining Microsoft Access, achieving 99.9% availability and monthly reporting in hours";
    const out = fitDescription(long);
    expect(out.length).toBeLessThanOrEqual(155);
    expect(out.endsWith("\u2026")).toBe(true);
    expect(long.startsWith(out.slice(0, -1))).toBe(true);
  });
});
