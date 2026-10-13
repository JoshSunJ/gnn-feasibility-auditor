import study from "../../docs/real-data-study.json";

export default function StudyEvidence() {
  return (
    <details className="study-evidence card">
      <summary>Checked on real graph data: PROTEINS and ENZYMES</summary>
      <p>
        Fixed training selections with the supplied continuous attributes and
        node labels preserved in the actual input tensors. Each result passed
        independent certificate replay.
      </p>
      <div className="study-grid">
        {study.cases.map((row) => (
          <article key={row.dataset}>
            <strong>{row.dataset}</strong>
            <span>
              {row.training_graphs.toLocaleString()} training graphs ·{" "}
              {row.node_count.toLocaleString()} nodes
            </span>
            <span>
              {row.input_contract.feature_dim} actual feature dimensions · 100%
              training ceiling
            </span>
            <a href={row.catalogue_url} target="_blank" rel="noreferrer">
              Dataset source ↗
            </a>
          </article>
        ))}
      </div>
      <p>
        These inputs had no forced label conflicts. A 100% ceiling is
        inconclusive: it guarantees neither successful training nor test
        accuracy. This is an input audit, not a model training benchmark.
        Selection, loader settings and reproducible scripts are recorded with
        the project.
      </p>
    </details>
  );
}
