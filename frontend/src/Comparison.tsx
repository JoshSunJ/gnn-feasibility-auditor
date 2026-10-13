import { useState } from "react";
import GraphPanel from "./GraphPanel";
import type { View, WLClass } from "./types";

export default function Comparison({ view }: { view: View }) {
  const classes = view.report.classes;
  const initial = classes.find((c) => c.unavoidable_errors > 0) ?? classes[0];
  const [a, setA] = useState(initial.graph_ids[0]);
  const [b, setB] = useState(initial.graph_ids[initial.graph_ids.length - 1]);
  const [t, setT] = useState(0);
  const graphs = view.dataset.graphs;
  const ai = graphs.findIndex((g) => g.id === a),
    bi = graphs.findIndex((g) => g.id === b);
  const rounds = view.report.certificate.rounds;
  const round = rounds[t];
  const classA = classes.find((c) => c.graph_ids.includes(a))!,
    classB = classes.find((c) => c.graph_ids.includes(b))!;
  const equivalent = classA.id === classB.id;
  const matching =
    JSON.stringify(round.histograms[ai]) ===
    JSON.stringify(round.histograms[bi]);
  const chooseClass = (c: WLClass) => {
    setA(c.graph_ids[0]);
    setB(c.graph_ids[c.graph_ids.length - 1]);
  };
  return (
    <section className="evidence" aria-label="Audit evidence">
      <aside className="classes">
        <div className="section-label">Equivalence classes</div>
        <h2>Where labels collide</h2>
        <p>
          Each class forces a shared prediction under the stated assumptions.
        </p>
        {classes.map((c) => (
          <button
            className={`class-card ${classA.id === c.id && equivalent ? "selected" : ""}`}
            key={c.id}
            onClick={() => chooseClass(c)}
            aria-pressed={classA.id === c.id && equivalent}
          >
            <strong>
              {c.id} · {c.size} graph{c.size === 1 ? "" : "s"}
            </strong>
            <span>
              {c.unavoidable_errors > 0 ? "Mixed labels" : "Consistent labels"}
            </span>
            <span>
              {c.label_counts
                .map((x, i) => `${view.class_label_text[c.id][i]} × ${x.count}`)
                .join(" · ")}
            </span>
            <small>
              At most {c.max_correct}/{c.size} correct
            </small>
          </button>
        ))}
      </aside>
      <div className="comparison card">
        <div className="comparison-heading">
          <div>
            <div className="section-label">Inspect the evidence</div>
            <h2>Compare two graphs</h2>
          </div>
          <span className={`badge ${equivalent ? "" : "neutral"}`}>
            {equivalent ? "Same stable WL class" : "Distinct stable WL classes"}
          </span>
        </div>
        <div className="selectors">
          {(["Graph A", "Graph B"] as const).map((title, i) => (
            <label key={title}>
              {title}
              <select
                value={i === 0 ? a : b}
                onChange={(e) => (i === 0 ? setA : setB)(e.target.value)}
              >
                {graphs.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.id}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <div className="graph-grid">
          <GraphPanel
            graph={graphs[ai]}
            label={view.graph_label_text[a]}
            title="Graph A"
            graphIndex={ai}
            round={round}
          />
          <GraphPanel
            graph={graphs[bi]}
            label={view.graph_label_text[b]}
            title="Graph B"
            graphIndex={bi}
            round={round}
          />
        </div>
        <label className="round-control">
          Refinement round <strong>{t}</strong>
          <input
            aria-label="Refinement round"
            type="range"
            min="0"
            max={rounds.length - 1}
            value={t}
            onChange={(e) => setT(Number(e.target.value))}
          />
          <span>
            {t === rounds.length - 1
              ? "Stable partition"
              : `${rounds.length - 1} rounds to inspect`}
          </span>
        </label>
        <p className="evidence-note">
          {matching
            ? "Exact color counts match at this round."
            : "Exact color counts differ at this round."}{" "}
          {equivalent
            ? "The stable evidence is indistinguishable under 1-WL."
            : "1-WL separates this pair; a particular GNN may still fail to fit it."}
        </p>
      </div>
    </section>
  );
}
