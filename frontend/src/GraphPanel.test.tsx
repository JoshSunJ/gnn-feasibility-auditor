import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import GraphPanel from "./GraphPanel";

test("large graph inspection searches every node while bounding option and histogram rendering", () => {
  const graph = {
    id: "large",
    nodes: Array.from({ length: 632 }, (_, i) => ({
      id: `node-${i}`,
      features: [i],
    })),
    edges: [],
  };
  const round = {
    round: 0,
    palette: graph.nodes.map((_, i) => [i, []]),
    node_colors: [graph.nodes.map((_, i) => i)],
    histograms: [graph.nodes.map((_, i) => [i, 1] as [number, number])],
  };
  render(
    <GraphPanel
      graph={graph}
      label="0"
      title="Graph A"
      graphIndex={0}
      round={round}
      stableOnly
    />,
  );
  expect(
    screen.getByText(/Topology display is limited to 500 nodes/),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("option")).toHaveLength(201);
  fireEvent.change(screen.getByLabelText("Find a node in Graph A"), {
    target: { value: "node-631" },
  });
  fireEvent.change(
    screen.getByRole("combobox", { name: "Inspect a node in Graph A" }),
    { target: { value: "631" } },
  );
  expect(screen.getByText("[631]").closest("p")).toHaveTextContent(
    "Actual features [631]",
  );
  expect(
    screen.getByText("Stable signature [color, neighbor color counts]"),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Next colors in Graph A" }),
  );
  expect(screen.getByText("632 exact colors · page 2/7")).toBeInTheDocument();
});
