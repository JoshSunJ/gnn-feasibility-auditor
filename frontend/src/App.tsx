import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { request } from "./api";
import { isActive, percent, type Config, type Job, type View } from "./types";

const Comparison = lazy(() => import("./Comparison"));

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [text, setText] = useState("");
  const [name, setName] = useState("No dataset selected");
  const [job, setJob] = useState<Job | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const active = isActive(job);
  useEffect(() => {
    request<Config>("/api/config")
      .then(setConfig)
      .catch(() =>
        setError(
          "The audit service is unavailable. Start the service, then reload this page.",
        ),
      );
  }, []);
  useEffect(() => {
    if (!job || !active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const next = await request<Job>(`/api/jobs/${job.id}`, {
          signal: controller.signal,
        });
        if (stopped) return;
        setJob(next);
        if (isActive(next)) timer = setTimeout(poll, 350);
      } catch (e) {
        if (!stopped) {
          setError((e as Error).message);
          setJob(null);
        }
      }
    };
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [job?.id, active]);
  useEffect(() => {
    if (job?.status !== "completed") return;
    const controller = new AbortController();
    request<View>(`/api/jobs/${job.id}/view`, { signal: controller.signal })
      .then(setView)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [job?.id, job?.status]);
  async function demo() {
    setError("");
    setBusy(true);
    try {
      const response = await fetch("/api/demo");
      if (!response.ok) throw new Error("Demo could not be loaded.");
      setText(await response.text());
      setName("Synthetic correctness fixture · 5 training graphs");
      setJob(null);
      setView(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function loadFile(chosen: File) {
    setError("");
    setJob(null);
    setView(null);
    if (config && chosen.size > config.limits.max_bytes) {
      setError(
        `File is too large. Maximum ${config.limits.max_bytes.toLocaleString()} bytes.`,
      );
      return;
    }
    setBusy(true);
    try {
      setText(await chosen.text());
      setName(chosen.name);
    } catch {
      setError(
        "The file could not be read. Choose a readable UTF-8 JSON file.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function run() {
    setError("");
    setView(null);
    setJob(null);
    setBusy(true);
    try {
      setJob(
        await request<Job>("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: text,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    if (!job) return;
    try {
      setJob(await request<Job>(`/api/jobs/${job.id}`, { method: "DELETE" }));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const summary = job?.status === "completed" ? job.summary : null;
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="/">
          ◈ <span>GNN Auditor</span>
        </a>
        <span className="version">Exact 1-WL · v0.2</span>
        <a href="/docs" target="_blank" rel="noreferrer">
          API reference ↗
        </a>
      </header>
      <section className="hero">
        <div className="section-label">Before you train</div>
        <h1>
          Can these graphs
          <br />
          receive different predictions?
        </h1>
        <p>
          Find training labels that conflict with a message-passing model’s
          representational limits. Inspect the graphs and export independently
          checked evidence.
        </p>
        <div className="hero-tags">
          <span>Actual node features</span>
          <span>Exact refinement</span>
          <span>Replayable certificates</span>
        </div>
      </section>
      <section className="workspace card" aria-label="Audit training inputs">
        <div className="input-heading">
          <div>
            <div className="section-label">01 / Training inputs</div>
            <h2>Start an audit</h2>
          </div>
          <button
            className="secondary"
            onClick={demo}
            disabled={busy || active}
          >
            Load demo
          </button>
        </div>
        <p>
          Supply only training graphs, after actual feature preprocessing. The
          demo is a synthetic correctness fixture.
        </p>
        <div className="upload-row">
          <button
            className="upload"
            onClick={() => file.current?.click()}
            disabled={active || busy}
          >
            <strong>Choose JSON file</strong>
            <span>{name}</span>
          </button>
          <input
            ref={file}
            aria-label="Upload training JSON"
            type="file"
            accept=".json,application/json"
            hidden
            onChange={(e) => {
              if (e.target.files?.[0]) void loadFile(e.target.files[0]);
              e.target.value = "";
            }}
          />
          <div className="scope">
            <strong>Supported scope</strong>
            <span>
              Simple undirected graphs · numeric float32/float64 node features ·
              one graph label per sample
            </span>
            {config && (
              <small>
                Up to {config.limits.max_graphs} graphs /{" "}
                {config.limits.max_nodes.toLocaleString()} nodes /{" "}
                {(config.limits.max_bytes / 1024 ** 2).toFixed(0)} MiB
              </small>
            )}
          </div>
        </div>
        <details className="paste">
          <summary>Paste or inspect dataset JSON</summary>
          <label>
            Original dataset JSON
            <textarea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setName("Pasted training JSON");
                setJob(null);
                setView(null);
              }}
              spellCheck={false}
              disabled={active || busy}
              placeholder="Paste the training JSON here. Use Load demo to see the complete format."
            />
          </label>
        </details>
        <details className="format">
          <summary>Input format and assumptions</summary>
          <p>
            Top-level fields: <code>schema_version: 1</code>,{" "}
            <code>split: train</code>,{" "}
            <code>graph_type: simple_undirected</code>,{" "}
            <code>feature_dtype</code>, <code>feature_dim</code>, and{" "}
            <code>graphs</code>. Each graph supplies <code>id</code>,{" "}
            <code>label</code>, explicit <code>nodes</code> with{" "}
            <code>features</code>, and unordered <code>edges</code>.
          </p>
          <p>
            Missing features, edge attributes, directed/multiple/self edges and
            extra inputs are rejected. The claim assumes shared deterministic
            message passing and an invariant multiset readout using these exact
            inputs. Node IDs and display positions are bookkeeping.
          </p>
        </details>
        <div className="run-row">
          <button
            className="primary"
            onClick={run}
            disabled={!text.trim() || !config || busy || active}
          >
            {busy ? "Submitting…" : "Run exact audit"}
          </button>
          <span>
            Temporary results · no accounts · no public dataset history
          </span>
        </div>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {job && (
          <div
            className={`job-state ${job.status}`}
            role="status"
            aria-live="polite"
          >
            <div>
              <strong>{job.status.replaceAll("_", " ")}</strong>
              {active && <span className="pulse" />}
            </div>
            <p>
              {job.error?.message ??
                (job.status === "completed"
                  ? "Certificate replay verified against the supplied inputs."
                  : job.status === "queued"
                    ? "Waiting for an available audit worker."
                    : "Refining the actual inputs and checking the certificate.")}
            </p>
            {job.progress && (
              <span>
                Round {job.progress.round} · {job.progress.color_count} exact
                colors
              </span>
            )}
            {active && (
              <button className="secondary" onClick={cancel}>
                Cancel audit
              </button>
            )}
          </div>
        )}
      </section>
      {summary && (
        <>
          <section className="results" aria-label="Verified training results">
            <div>
              <span>Training accuracy upper bound</span>
              <strong>{percent(summary.training_accuracy_upper_bound)}</strong>
              <small>
                {summary.training_accuracy_upper_bound.max_correct} of{" "}
                {summary.training_accuracy_upper_bound.total} labels at most
              </small>
            </div>
            <div>
              <span>Unavoidable training errors</span>
              <strong>{summary.unavoidable_training_errors}</strong>
              <small>{summary.graph_count} training samples</small>
            </div>
            <div>
              <span>Conflicting graph pairs</span>
              <strong>{summary.conflicting_pair_count}</strong>
              <small>{summary.class_count} stable WL classes</small>
            </div>
          </section>
          <div className="exports">
            <span>
              Verified in {job!.runtime_seconds.toFixed(2)}s · sampled peak{" "}
              {job!.peak_memory_mb} MiB
            </span>
            <div>
              <a href={`/api/jobs/${job!.id}/report`}>Certificate JSON ↓</a>
              <a href={`/api/jobs/${job!.id}/inputs`}>Actual inputs ↓</a>
              <a
                href={`/api/jobs/${job!.id}/explorer`}
                target="_blank"
                rel="noreferrer"
              >
                Offline report ↗
              </a>
            </div>
          </div>
          {view ? (
            <Suspense fallback={<p role="status">Loading graph viewer…</p>}>
              <Comparison key={job!.id} view={view} />
            </Suspense>
          ) : (
            <p role="status">Loading verified evidence…</p>
          )}
          <p className="expiry">
            Results expire{" "}
            {job?.expires_at
              ? new Date(job.expires_at * 1000).toLocaleTimeString()
              : ""}{" "}
            and are lost on service restart. Download the certificate and inputs
            to keep and replay the result.
          </p>
        </>
      )}
      <footer>
        <strong>Training-set representational limit.</strong> This ceiling does
        not predict test accuracy. A 100% ceiling means no forced label conflict
        was found; it does not guarantee trainability. Matching stable WL
        evidence does not establish graph isomorphism.
      </footer>
    </main>
  );
}
