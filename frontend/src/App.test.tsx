import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

vi.mock("./Comparison", () => ({
  default: () => <div>Verified graph comparison</div>,
}));
const config = {
  limits: {
    max_bytes: 1000,
    max_graphs: 128,
    max_nodes: 2048,
    max_edges: 8192,
    max_feature_dim: 64,
    timeout_seconds: 20,
    ttl_seconds: 900,
  },
  scope: "supported",
  storage: "temporary",
};
const raw = '{"label":900719925474099312345}';
const completed = {
  id: "opaque",
  status: "completed",
  summary: {
    certificate_verified: true,
    graph_count: 5,
    node_count: 30,
    class_count: 3,
    training_accuracy_upper_bound: {
      max_correct: 4,
      total: 5,
      fraction: "4/5",
      value: 0.8,
    },
    unavoidable_training_errors: 1,
    conflicting_pair_count: 2,
  },
  progress: null,
  error: null,
  expires_at: 1800000000,
  runtime_seconds: 0.5,
  peak_memory_mb: 25,
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => vi.unstubAllGlobals());

test("demo sends original JSON text and only completed jobs expose verified results", async () => {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/config") return json(config);
    if (url === "/api/demo") return new Response(raw);
    if (url === "/api/jobs") {
      expect(init?.body).toBe(raw);
      return json({ ...completed, status: "queued", summary: null }, 202);
    }
    if (url.endsWith("/view")) return json({});
    return json(completed);
  });
  vi.stubGlobal("fetch", fetch);
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Load demo" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run exact audit" }),
    ).toBeEnabled(),
  );
  expect(screen.queryByText("80%")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Run exact audit" }));
  expect(await screen.findByText("80%")).toBeInTheDocument();
  expect(
    await screen.findByText("Verified graph comparison"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Certificate JSON ↓" }),
  ).toHaveAttribute("href", "/api/jobs/opaque/report");
  fireEvent.change(screen.getByLabelText("Original dataset JSON"), {
    target: { value: '{"changed":true}' },
  });
  expect(screen.queryByText("80%")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Certificate JSON ↓" }),
  ).not.toBeInTheDocument();
});

test("rejected audit shows field error and no ceiling or downloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url === "/api/config"
        ? json(config)
        : json({
            ...completed,
            status: "rejected",
            summary: null,
            error: {
              code: "invalid_input",
              message: "graphs[0].nodes[0]: missing features",
            },
          }),
    ),
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Original dataset JSON"), {
    target: { value: "{}" },
  });
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run exact audit" }),
    ).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Run exact audit" }));
  expect(
    await screen.findByText("graphs[0].nodes[0]: missing features"),
  ).toBeInTheDocument();
  expect(screen.queryByText("80%")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Certificate JSON ↓" }),
  ).not.toBeInTheDocument();
});

test("cancellation clears active state without publishing a ceiling", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) =>
      url === "/api/config"
        ? json(config)
        : json({
            ...completed,
            summary: null,
            status: init?.method === "DELETE" ? "cancelled" : "running",
            error:
              init?.method === "DELETE"
                ? {
                    code: "cancelled",
                    message: "Audit cancelled. No ceiling was certified.",
                  }
                : null,
          }),
    ),
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Original dataset JSON"), {
    target: { value: "{}" },
  });
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run exact audit" }),
    ).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Run exact audit" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel audit" }));
  expect(
    await screen.findByText("Audit cancelled. No ceiling was certified."),
  ).toBeInTheDocument();
  expect(screen.queryByText("80%")).not.toBeInTheDocument();
});

test("oversized files are rejected before upload", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json(config)),
  );
  render(<App />);
  await waitFor(() =>
    expect(screen.getByText(/Up to 128 graphs/)).toBeInTheDocument(),
  );
  fireEvent.change(screen.getByLabelText("Upload training JSON"), {
    target: {
      files: [
        new File(["x".repeat(1001)], "large.json", {
          type: "application/json",
        }),
      ],
    },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "File is too large",
  );
});
