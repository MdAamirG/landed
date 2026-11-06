import { describe, expect, it } from "vitest";

import { measure, problemWith, stripText } from "./capture";

const SIZE = 40;

/** A square image from a function of each pixel's position. */
function image(pixel: (x: number, y: number) => number): number[] {
  const grey: number[] = [];
  for (let y = 0; y < SIZE; y += 1) {
    for (let x = 0; x < SIZE; x += 1) grey.push(pixel(x, y));
  }
  return grey;
}

describe("the phone check", () => {
  it("passes a bright image with hard edges", () => {
    const checker = image((x, y) => ((x + y) % 2 === 0 ? 255 : 60));

    expect(problemWith(measure(checker, SIZE, SIZE))).toBeNull();
  });

  it("calls a smooth image blurred", () => {
    const gradient = image((x) => 120 + x);

    expect(problemWith(measure(gradient, SIZE, SIZE))).toBe("blurred");
  });

  it("calls a dark image dark, even with hard edges", () => {
    const dim = image((x, y) => ((x + y) % 2 === 0 ? 40 : 0));

    expect(problemWith(measure(dim, SIZE, SIZE))).toBe("dark");
  });
});

describe("the printed strip", () => {
  const taken = new Date("2026-11-07T09:22:00Z");

  it("carries the trip, India time and coordinates", () => {
    const text = stripText("TRP-66134", taken, { lat: 19.8762, lng: 75.3433, accuracyM: 12 });

    expect(text).toContain("TRP-66134");
    expect(text).toContain("14:52 IST");
    expect(text).toContain("19.87620, 75.34330");
  });

  it("says when there is no location", () => {
    expect(stripText("TRP-66134", taken, null)).toContain("no location");
  });
});
