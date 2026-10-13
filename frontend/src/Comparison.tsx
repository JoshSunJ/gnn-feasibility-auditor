import { useState } from "react";
import GraphPanel from "./GraphPanel";
import type { View, WLClass } from "./types";

export default function Comparison({ view }: { view: View }) {
  const classes = view.report.classes;
  const initial = classes.find((c) => c.unavoidable_errors > 0) ?? classes[0];
  const pairFor = (c: WLClass) => {
    const first = c.graph_ids[0];
    return [
      first,
      c.graph_ids.find(
        (id) => view.graph_label_text[id] !== view.graph_label_text[first],
      ) ?? c.graph_ids[c.graph_ids.length - 1],
    ];
  };
  const [a, setA] = useState(initial.graph_ids[0]);
  const [b, setB] = useState(pairFor(initial)[1]);
  const [t, setT] = useState(0);
  const [query, setQuery] = useState("");
  const [onlyConflicts, setOnlyConflicts] = useState(
    classes.some((c) => c.unavoidable_errors > 0),
  );
  const [page, setPage] = useState(0);
  const graphs = view.dataset.graphs;
  const ai = graphs.findIndex((g) => g.id === a),
    bi = graphs.findIndex((g) => g.id === b);
  const compact = view.inspection?.mode === "stable_only";
  const rounds = view.inspection?.rounds ?? view.report.certificate.rounds!;
  const round = rounds[t];
  const classA = classes.find((c) => c.graph_ids.includes(a))!,
    classB = classes.find((c) => c.graph_ids.includes(b))!;
  const equivalent = classA.id === classB.id;
  const matching =
    JSON.stringify(round.histograms[ai]) ===
    JSON.stringify(round.histograms[bi]);
  const chooseClass = (c: WLClass) => {
    const [first, second] = pairFor(c);
    setA(first);
    setB(second);
  };
  const matchingClasses = classes.filter(
    (c) =>
      (!onlyConflicts || c.unavoidable_errors > 0) &&
      `${c.id} ${c.graph_ids.join(" ")} ${view.class_label_text[c.id].join(" ")}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const pageCount = Math.max(1, Math.ceil(matchingClasses.length / 20));
  return (
    <section className="evidence" aria-label="Audit evidence">
      <aside className="classes">
        <div className="section-label">Equivalence classes</div>
        <h2>
          {classes.some((c) => c.unavoidable_errors > 0)
            ? "Where labels collide"
            : "No forced label conflicts"}
        </h2>
        <p>
          Each class forces a shared prediction under the stated assumptions.
        </p>
        <label className="class-search">
          Find a class or graph
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder="Graph ID, class or label"
          />
        </label>
        <label className="class-filter">
          <input
            type="checkbox"
            checked={onlyConflicts}
            onChange={(e) => {
              setOnlyConflicts(e.target.checked);
              setPage(0);
            }}
          />
          Conflicting classes only
        </label>
        <small>
          {matchingClasses.length} matching classes · page {page + 1}/
          {pageCount}
        </small>
        {matchingClasses.length === 0 && <p>No classes match these filters.</p>}
        <div className="class-results" key={page}>
          {matchingClasses.slice(page * 20, (page + 1) * 20).map((c) => (
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
                {c.unavoidable_errors > 0
                  ? "Mixed labels"
                  : "Consistent labels"}
              </span>
              <span>
                {c.label_counts
                  .map(
                    (x, i) => `${view.class_label_text[c.id][i]} × ${x.count}`,
                  )
                  .join(" · ")}
              </span>
              <small>
                At most {c.max_correct}/{c.size} correct
              </small>
            </button>
          ))}
        </div>
        {pageCount > 1 && (
          <div className="class-pages">
            <button
              className="secondary"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous classes
            </button>
            <button
              className="secondary"
              disabled={page + 1 === pageCount}
              onClick={() => setPage(page + 1)}
            >
              Next classes
            </button>
          </div>
        )}
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
            stableOnly={compact}
          />
          <GraphPanel
            graph={graphs[bi]}
            label={view.graph_label_text[b]}
            title="Graph B"
            graphIndex={bi}
            round={round}
            stableOnly={compact}
          />
        </div>
        <label className="round-control">
          {compact ? "Final stable colors" : "Refinement round"}{" "}
          <strong>{compact ? "" : t}</strong>
          <input
            aria-label="Refinement round"
            type="range"
            min="0"
            max={rounds.length - 1}
            value={t}
            disabled={compact}
            onChange={(e) => setT(Number(e.target.value))}
          />
          <span>
            {compact
              ? "Compact split certificate; no round trace"
              : t === rounds.length - 1
                ? "Stable partition"
                : `${rounds.length - 1} rounds to inspect`}
          </span>
        </label>
        <p className="evidence-note">
          {matching
            ? compact
              ? "Exact stable color counts match."
              : "Exact color counts match at this round."
            : compact
              ? "Exact stable color counts differ."
              : "Exact color counts differ at this round."}{" "}
          {equivalent
            ? "The stable evidence is indistinguishable under 1-WL."
            : "1-WL separates this pair; a particular GNN may still fail to fit it."}
        </p>
      </div>
    </section>
  );
}
