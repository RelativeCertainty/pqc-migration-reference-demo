import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InventorySection, PrioritizationSection } from "./components/InventoryRisk";
import { ArchitectureSection } from "./components/OverviewArchitecture";
import { DashboardSection, PostureSection } from "./components/PostureDashboard";
import { parseRuntimePosture } from "./hooks/usePosture";
import stylesSource from "./reference.css?raw";

function posturePayload(hostname = "pqc-demo.example.invalid") {
  return {
    schema_version: "pqc-posture.v3",
    evidence_tier: "request_transport_observation",
    observed_at: "2026-08-13T23:04:32.000Z",
    hostname,
    request_transport: {
      tls_version: { state: "observed", value: "TLSv1.3" },
      tls_cipher: { state: "observed", value: "AEAD-AES128-GCM-SHA256" },
      http_protocol: { state: "observed", value: "HTTP/2" },
      exact_session_key_exchange: { state: "not_observable", explanation: "Not exposed by this handler." },
    },
    hostname_capability: { state: "not_observable_by_handler", explanation: "Requires separate exact-host evidence." },
    visitor_edge_post_quantum_signatures: { state: "not_deployed", explanation: "Not deployed or claimed." },
    access_control: { state: "synthetic_session_only", target: "C# assessment-scoped demo authorization" },
    evidence_separation: {
      algorithm_standards: "Documentary algorithm evidence only.",
      cryptographic_module: "No module validation asserted.",
    },
    data_posture: { storage: "isolated_sqlite", upstream_origin_dependency: "none", dataset: "synthetic_only", request_logging: "not_implemented_by_application" },
    approved_deployment_label: { label: "PQC migration reference package", eligible: false, reason: "Required evidence remains separate." },
  };
}

beforeAll(() => {
  Object.defineProperty(window, "scrollTo", { value: vi.fn(), writable: true });
  Object.defineProperty(Element.prototype, "scrollIntoView", { value: vi.fn(), writable: true });
});

describe("reference demo navigation and interactions", () => {
  it("keeps the posture parser aligned to the canonical UTC v3 contract", () => {
    expect(parseRuntimePosture(posturePayload())).toMatchObject({
      schema_version: "pqc-posture.v3",
      hostname: "pqc-demo.example.invalid",
    });
    expect(parseRuntimePosture({ ...posturePayload(), observed_at: "2026-08-13T23:04:32Z" })).toBeDefined();
    expect(parseRuntimePosture({ ...posturePayload(), observed_at: "2026-08-13T23:04:32.123456789Z" })).toBeDefined();
    expect(() => parseRuntimePosture({ ...posturePayload(), observed_at: "2026-08-13T17:04:32-06:00" })).toThrow("unexpected posture contract");
    expect(() => parseRuntimePosture({ ...posturePayload(), extra: true })).toThrow("unexpected posture contract");
  });

  it("filters the 10-row synthetic inventory", async () => {
    const user = userEvent.setup();
    render(<InventorySection />);
    const table = screen.getByRole("table", { name: "Synthetic seed inventory with canonical fusion annotations" });
    expect(within(table).getByText("Customer API Gateway")).toBeInTheDocument();
    expect(within(table).getByText("Research Archive Encryptor")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Illustrative priority"), "Urgent");
    expect(within(table).getByText("Customer API Gateway")).toBeInTheDocument();
    expect(within(table).queryByText("Research Archive Encryptor")).not.toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search inventory"), { target: { value: "no matching system" } });
    expect(screen.getByText("No synthetic systems match the current filters.")).toBeInTheDocument();
  });

  it("shows the ports-and-adapters evidence-fusion path and all five modeled feeds", () => {
    render(<ArchitectureSection />);

    expect(screen.getByRole("heading", { name: "Adapters isolate feeds. A neutral contract protects the core." })).toBeInTheDocument();
    expect(screen.getByLabelText("Ports and adapters evidence-fusion path")).toHaveTextContent("EvidenceObservation v1");
    expect(screen.getByLabelText("Ports and adapters evidence-fusion path")).toHaveTextContent("CanonicalCryptoRecord v1");
    expect(screen.getByText("Expanded seed observations").parentElement).toHaveTextContent("36");
    expect(screen.getByText("Enrichment submissions").parentElement).toHaveTextContent("12");
    expect(screen.getByText("Retained enrichment").parentElement).toHaveTextContent("11");
    for (const feed of ["ExtraHop Internet TLS + certificates", "Vulnerability manager", "PKI inventory", "SAST", "CMDB"]) {
      expect(screen.getByRole("heading", { name: feed })).toBeInTheDocument();
    }
    expect(screen.getAllByText("MODELED · NOT CONNECTED")).toHaveLength(5);
  });

  it("projects canonical correlation state and a review queue into inventory", async () => {
    const user = userEvent.setup();
    render(<InventorySection />);

    expect(screen.getByRole("heading", { name: "Records that need human review" })).toBeInTheDocument();
    expect(screen.getByText("orphan-service-77")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Synthetic seed inventory with canonical fusion annotations" });
    const payment = within(table).getByText("Internal Java Payment Service", { selector: "strong" }).closest("tr");
    expect(payment).not.toBeNull();
    expect(within(payment as HTMLTableRowElement).getByText("Identity / classification conflict", { selector: "strong.correlation-state" })).toBeInTheDocument();
    expect(within(payment as HTMLTableRowElement).getByText("1 exact duplicate submissions ignored", { selector: "small" })).toBeInTheDocument();
    await user.click(within(payment as HTMLTableRowElement).getByText("Explain record"));
    const detailValue = within(table).getByText("displayName · estateClass");
    expect(detailValue).toBeInTheDocument();
    expect(detailValue.closest("td")).toHaveAttribute("colspan", "9");
    expect(within(payment as HTMLTableRowElement).getByRole("button", { name: "Hide record explanation" })).toHaveAttribute("aria-expanded", "true");
    await user.click(within(table).getByRole("button", { name: "Close details" }));
    expect(within(table).queryByText("displayName · estateClass")).not.toBeInTheDocument();
  });

  it("defines evidence-matching language and table columns in plain language", () => {
    render(<InventorySection />);

    expect(screen.getByRole("heading", { name: "How to read the evidence-matching terms" })).toBeInTheDocument();
    expect(screen.getByText("Unmatched", { selector: ".inventory-reading-guide h3" }).parentElement).toHaveTextContent("One side of the join is missing");
    expect(screen.getByText("Conflict", { selector: ".inventory-reading-guide h3" }).parentElement).toHaveTextContent("disagree on a governed field");
    expect(screen.getByText("Correlated", { selector: ".inventory-reading-guide h3" }).parentElement).toHaveTextContent("initial inventory and at least one enrichment feed");
    expect(screen.getByText("Candidate", { selector: ".inventory-reading-guide h3" }).parentElement).toHaveTextContent("not a confirmed system");
    expect(screen.getByText("Change route / concern", { selector: ".inventory-table thead span" }).parentElement).toHaveTextContent("Who changes it / why it matters");
    expect(screen.getByText("Seed-to-enrichment match", { selector: ".inventory-table thead span" }).parentElement).toHaveTextContent("How synthetic feeds relate to the seed");
    expect(screen.getByText("Seed + fusion details", { selector: ".inventory-table thead span" }).parentElement).toHaveTextContent("Authority / gaps / review");
    expect(screen.getByText("Nine-column dictionary")).toBeInTheDocument();

    const table = screen.getByRole("table", { name: "Synthetic seed inventory with canonical fusion annotations" });
    const headings = within(table).getAllByRole("columnheader");
    expect(headings).toHaveLength(9);
    for (const row of within(table).getAllByRole("row").slice(1)) {
      const cells = within(row).getAllByRole("cell");
      expect(cells).toHaveLength(headings.length);
      expect(cells.every((cell) => cell.hasAttribute("data-label"))).toBe(true);
    }
  });

  it("does not reintroduce intentional horizontal panning", () => {
    expect(stylesSource).not.toMatch(/overflow-x\s*:\s*(?:auto|scroll)/i);
    expect(stylesSource).not.toMatch(/overflow\s*:\s*[^;]*(?:auto|scroll)[^;]*;/i);
  });

  it("filters inventory by software estate while keeping issue type separate", async () => {
    const user = userEvent.setup();
    render(<InventorySection />);
    const table = screen.getByRole("table", { name: "Synthetic seed inventory with canonical fusion annotations" });

    await user.selectOptions(screen.getByLabelText("Change-control class"), "third-party-saas");

    expect(within(table).getByText("Customer API Gateway")).toBeInTheDocument();
    expect(within(table).getByText("Mobile Identity Broker")).toBeInTheDocument();
    expect(within(table).queryByText("Internal Java Payment Service")).not.toBeInTheDocument();
    expect(within(table).getAllByText("TLS / protocol").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Change control determines route; concern type says why")).toHaveLength(2);
  });

  it("gives visual score and distribution indicators programmatic names", () => {
    const priority = render(<PrioritizationSection />);
    expect(screen.getByLabelText(/^Illustrative priority score: \d+ out of 100$/)).toHaveProperty("tagName", "METER");
    priority.unmount();

    render(<DashboardSection />);
    const distributions = screen.getAllByRole("progressbar");
    expect(distributions.length).toBeGreaterThan(0);
    expect(distributions.every((item) => item.getAttribute("aria-label")?.includes("seed systems"))).toBe(true);
  });

  it("offers bounded recovery when the posture endpoint is temporarily unavailable", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce(new Response(JSON.stringify(posturePayload()), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PostureSection />);
    const retry = await screen.findByRole("button", { name: "Retry bounded posture check" });
    await user.click(retry);

    await waitFor(() => expect(screen.getByText("TLSv1.3")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: "Retry bounded posture check" })).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("keeps a runtime observation separate from the source-only descriptor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(posturePayload("127.0.0.1")), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PostureSection />);

    expect(await screen.findByText(/Runtime metadata came from the current execution context/)).toHaveTextContent("127.0.0.1");
    expect(screen.getByText(/does not change the source-only status/)).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("fails closed when a posture response names v3 but omits its contract fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ schema_version: "pqc-posture.v3" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PostureSection />);

    expect(await screen.findByRole("button", { name: "Retry bounded posture check" })).toBeInTheDocument();
    expect(screen.getByText(/unexpected posture contract/)).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
