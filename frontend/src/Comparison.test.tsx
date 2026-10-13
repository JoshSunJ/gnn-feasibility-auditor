import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import Comparison from "./Comparison";
import type { View } from "./types";

vi.mock("./GraphPanel", () => ({ default: () => <div>Graph inspector</div> }));

function fixture(): View {
  const ids = [
    "first",
    "conflict",
    "last",
    ...Array.from({ length: 24 }, (_, i) => `g${i}`),
  ];
  const classes = [
    {
      id: "WL0001",
      graph_ids: ids.slice(0, 3),
      size: 3,
      max_correct: 2,
      unavoidable_errors: 1,
      label_counts: [{ count: 2 }, { count: 1 }],
    },
    ...ids.slice(3).map((id, i) => ({
      id: `WL${i + 2}`,
      graph_ids: [id],
      size: 1,
      max_correct: 1,
      unavoidable_errors: 0,
      label_counts: [{ count: 1 }],
    })),
  ];
  return {
    dataset: {
      graphs: ids.map((id) => ({ id, nodes: [], edges: [] })),
      feature_dtype: "float64",
      feature_dim: 1,
    },
    report: { classes, certificate: {} },
    inspection: {
      mode: "stable_only",
      rounds: [
        {
          round: 0,
          palette: [],
          node_colors: ids.map(() => []),
          histograms: ids.map(() => []),
        },
      ],
    },
    graph_label_text: Object.fromEntries(
      ids.map((id) => [
        id,
        id === "conflict" ? "900719925474099312346" : "900719925474099312345",
      ]),
    ),
    class_label_text: Object.fromEntries(
      classes.map((c) => [c.id, c.unavoidable_errors ? ["a", "b"] : ["a"]]),
    ),
  };
}

test("compact inspection selects differing exact labels and provides honest final-only evidence", () => {
  render(<Comparison view={fixture()} />);
  expect(screen.getByRole("combobox", { name: "Graph B" })).toHaveValue(
    "conflict",
  );
  expect(
    screen.getByRole("slider", { name: "Refinement round" }),
  ).toBeDisabled();
  expect(
    screen.getByText("Compact split certificate; no round trace"),
  ).toBeInTheDocument();
  expect(screen.getByText("1 matching classes · page 1/1")).toBeInTheDocument();
});

test("large class lists support conflict filtering, pagination and graph search", () => {
  render(<Comparison view={fixture()} />);
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Conflicting classes only" }),
  );
  expect(
    screen.getByText("25 matching classes · page 1/2"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Next classes" }));
  expect(
    screen.getByText("25 matching classes · page 2/2"),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Find a class or graph"), {
    target: { value: "g23" },
  });
  expect(screen.getByText("1 matching classes · page 1/1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /WL25 · 1 graph/ }));
  expect(screen.getByRole("combobox", { name: "Graph A" })).toHaveValue("g23");
});
