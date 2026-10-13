import { expect, test } from "vitest";
import { percent } from "./types";

test("an unavoidable training error never rounds into an apparent 100% ceiling", () => {
  expect(
    percent({
      max_correct: 2047,
      total: 2048,
      fraction: "2047/2048",
      value: 2047 / 2048,
    }),
  ).toBe("99.95%");
  expect(
    percent({
      max_correct: 999999,
      total: 1000000,
      fraction: "999999/1000000",
      value: 999999 / 1000000,
    }),
  ).toBe("<100%");
  expect(
    percent({ max_correct: 4, total: 5, fraction: "4/5", value: 0.8 }),
  ).toBe("80%");
  expect(percent({ max_correct: 5, total: 5, fraction: "1", value: 1 })).toBe(
    "100%",
  );
});
