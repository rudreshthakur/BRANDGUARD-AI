import { describe, expect, it } from "vitest";
import { segment } from "./segments";
import { citation } from "./format";

describe("segment", () => {
  it("returns a single plain segment without marks", () => {
    expect(segment("hello", [])).toEqual([{ text: "hello", mark: null }]);
  });
  it("splits around a mark and preserves all text", () => {
    const segs = segment("improves productivity by 50% today", [{ id: "a", start: 22, end: 28, kind: "gap" }]);
    expect(segs.map((s) => s.text).join("")).toBe("improves productivity by 50% today");
    expect(segs.find((s) => s.mark)?.text).toBe("by 50%");
  });
  it("gives overlapping characters to the earlier (higher priority) mark", () => {
    const segs = segment("abcdef", [
      { id: "hi", start: 1, end: 4, kind: "rule" },
      { id: "lo", start: 2, end: 6, kind: "gap" },
    ]);
    expect(segs.map((s) => [s.text, s.mark?.id ?? null])).toEqual([["a", null], ["bcd", "hi"], ["ef", "lo"]]);
  });
  it("ignores out-of-range marks safely", () => {
    expect(segment("abc", [{ id: "x", start: 10, end: 20, kind: "rule" }])).toEqual([{ text: "abc", mark: null }]);
  });
});

describe("citation", () => {
  it("formats document, page and section", () => {
    expect(citation({ document: "Spec Sheet v2", version: 2, page: 1, section: "Beacon" })).toBe("Spec Sheet v2, p. 1, Beacon");
  });
  it("adds version when the title lacks one", () => {
    expect(citation({ document: "Guidelines", version: 3, page: null, section: null })).toBe("Guidelines (v3)");
  });
});
