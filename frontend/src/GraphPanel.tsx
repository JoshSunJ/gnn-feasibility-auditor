import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { Graph, Round } from "./types";

export default function GraphPanel({
  graph,
  label,
  title,
  graphIndex,
  round,
}: {
  graph: Graph;
  label: string;
  title: string;
  graphIndex: number;
  round: Round;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const colors = round.node_colors[graphIndex];
  useEffect(() => {
    setSelected(null);
  }, [graph.id]);
  useEffect(() => {
    if (!container.current || graph.nodes.length > 500) return;
    const index = new Map(graph.nodes.map((node, i) => [node.id, i]));
    const cy = cytoscape({
      container: container.current,
      elements: [
        ...graph.nodes.map((node, i) => ({
          data: {
            id: `n${i}`,
            index: i,
            label: `c${colors[i]}`,
            color: `hsl(${(colors[i] * 137.508 + 150) % 360}, 32%, 70%)`,
          },
        })),
        ...graph.edges.map(([u, v], i) => ({
          data: {
            id: `e${i}`,
            source: `n${index.get(u)}`,
            target: `n${index.get(v)}`,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            "font-size": 12,
            "text-valign": "center",
            width: 34,
            height: 34,
          },
        },
        { selector: "edge", style: { width: 1.5, "line-color": "#afb9b5" } },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#25483b" },
        },
      ],
      layout: { name: "preset" },
      minZoom: 0.2,
      maxZoom: 4,
    });
    const components = cy.elements().components();
    const cols = Math.max(1, Math.ceil(Math.sqrt(components.length)));
    components.forEach((component, c) => {
      const nodes = component.nodes();
      nodes.forEach((node, i) => {
        const theta =
          (2 * Math.PI * i) / Math.max(1, nodes.length) - Math.PI / 2;
        const radius =
          nodes.length > 1 ? Math.max(45, Math.min(110, nodes.length * 8)) : 0;
        node.position({
          x: (c % cols) * 280 + 130 + radius * Math.cos(theta),
          y: Math.floor(c / cols) * 280 + 130 + radius * Math.sin(theta),
        });
      });
    });
    cy.fit(undefined, 25);
    cy.on("tap", "node", (event) =>
      setSelected(event.target.data("index") as number),
    );
    const resize = new ResizeObserver(() => {
      cy.resize();
      cy.fit(undefined, 25);
    });
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      cy.destroy();
    };
  }, [graph, colors]);
  const node = selected === null ? null : graph.nodes[selected];
  const histogram = round.histograms[graphIndex];
  return (
    <article className="graph-panel">
      <div className="graph-meta">
        <strong>{title}</strong>
        <span>
          Label {label} · {graph.nodes.length} nodes · {graph.edges.length}{" "}
          edges
        </span>
      </div>
      {graph.nodes.length > 500 ? (
        <p className="note">
          Topology display is limited to 500 nodes. All nodes remain in the
          audit and exports; use the node inspector below.
        </p>
      ) : (
        <div
          ref={container}
          className="graph-canvas"
          role="img"
          aria-label={`${title} topology and round ${round.round} colors`}
        />
      )}
      {!graph.nodes.length && <p>This graph has no nodes.</p>}
      <div className="histogram" aria-label={`${title} exact color counts`}>
        {histogram.map(([color, count]) => (
          <span key={color}>
            c{color} × {count}
          </span>
        ))}
      </div>
      <label className="node-label">
        Inspect a node in {title}
        <select
          value={selected ?? ""}
          disabled={!graph.nodes.length}
          onChange={(e) =>
            setSelected(e.target.value === "" ? null : Number(e.target.value))
          }
        >
          <option value="">Select a node or click the graph</option>
          {graph.nodes.map((n, i) => (
            <option key={n.id} value={i}>
              {n.id}
            </option>
          ))}
        </select>
      </label>
      {node && selected !== null && (
        <div className="node-detail">
          <strong>Node {node.id}</strong>
          <p>
            Actual features <code>{JSON.stringify(node.features)}</code>
          </p>
          <p>Color c{colors[selected]}</p>
          <p>Exact refinement signature</p>
          <code className="signature">
            {JSON.stringify(round.palette[colors[selected]])}
          </code>
        </div>
      )}
    </article>
  );
}
