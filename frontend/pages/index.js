import { useState } from "react";
import Head from "next/head";

const numericFields = [
  ["budget_inr", "Budget (INR)"],
  ["min_turnover_cr", "Minimum turnover (crore INR)"],
  ["emd_required_inr", "Required EMD (INR)"],
  ["min_local_content_pct", "Minimum local content (%)"],
  ["min_warranty_years", "Minimum warranty (years)"],
];
const defaultChecks = [
  "gst_registration",
  "gst_returns",
  "pan",
  "income_tax",
  "debarment",
];
const emptyTender = {
  tender_id: "",
  title: "",
  requirements: Object.fromEntries(numericFields.map(([key]) => [key, ""])),
  required_checks: defaultChecks,
  confirmation_note: "",
};
function Badge({ value }) {
  return (
    <span className={`status status-${String(value).toLowerCase()}`}>
      {String(value).replaceAll("_", " ")}
    </span>
  );
}

export default function Home() {
  const [accessKey, setAccessKey] = useState("");
  const [checks, setChecks] = useState([]);
  const [tender, setTender] = useState(emptyTender);
  const [confirmedTender, setConfirmedTender] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [audit, setAudit] = useState(null);
  const [history, setHistory] = useState([]);
  const [mode, setMode] = useState("live");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);
  const [decision, setDecision] = useState("REQUEST_CLARIFICATION");
  const [reason, setReason] = useState("");
  const [override, setOverride] = useState({
    clause_id: "",
    new_status: "PENDING",
    justification: "",
  });
  const [nicCode, setNicCode] = useState("26");
  const [nic, setNic] = useState(null);

  async function api(path, options = {}, binary = false) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "X-BidLens-Key": accessKey,
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const body = await response.json();
        detail =
          typeof body.detail === "string"
            ? body.detail
            : "Please check the required fields and values.";
      } catch {}
      throw new Error(detail);
    }
    return binary ? response.blob() : response.json();
  }
  async function perform(action) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function refreshHistory() {
    const data = await api("/audit/list");
    setHistory(data.audits);
  }
  function changeTender(next) {
    setTender(next);
    setConfirmedTender(null);
  }
  function applyAudit(result) {
    setAudit(result);
    setReason("");
    setOverride({ clause_id: "", new_status: "PENDING", justification: "" });
  }

  async function connect() {
    await perform(async () => {
      const data = await api("/system/checks");
      setChecks(data.checks);
      await refreshHistory();
      setConnected(true);
      setMessage("Connected to the configured pilot officer account.");
    });
  }
  async function uploadTender(file) {
    if (!file) return;
    await perform(async () => {
      const body = new FormData();
      body.append("file", file);
      const { tender_data: data } = await api("/document/tender/upload", {
        method: "POST",
        body,
      });
      changeTender({
        ...emptyTender,
        tender_id: data.tender_id || "",
        title: data.title,
        tender_file_id: data.tender_file_id,
        requirements: Object.fromEntries(
          numericFields.map(([key]) => [key, data.requirements[key] ?? ""]),
        ),
      });
      setMessage(
        "Draft extracted. Confirm each value and the scope below. Missing values stay unknown.",
      );
    });
  }
  async function confirmTender() {
    await perform(async () => {
      const requirements = Object.fromEntries(
        numericFields.map(([key]) => [
          key,
          tender.requirements[key] === ""
            ? null
            : Number(tender.requirements[key]),
        ]),
      );
      const result = await api("/document/tender/confirm", {
        method: "POST",
        body: JSON.stringify({ ...tender, requirements }),
      });
      setConfirmedTender(result.tender);
      setMessage(
        "Tender version saved. This exact version will govern the evaluation.",
      );
    });
  }
  async function uploadBids(files) {
    await perform(async () => {
      const uploaded = [];
      for (const file of files) {
        const body = new FormData();
        body.append("file", file);
        try {
          uploaded.push(
            await api("/document/upload", { method: "POST", body }),
          );
        } catch (err) {
          setAttachments((previous) => [...previous, ...uploaded]);
          throw err;
        }
      }
      setAttachments((previous) => [...previous, ...uploaded]);
      setMessage(
        `${uploaded.length} attachment(s) added to this bidder's submission.`,
      );
    });
  }
  async function runAudit() {
    await perform(async () => {
      const result = await api("/audit/run", {
        method: "POST",
        body: JSON.stringify({
          file_ids: attachments.map((d) => d.file_id),
          tender_version_id: confirmedTender.version_id,
          mode,
        }),
      });
      applyAudit(result.results);
      await refreshHistory();
      setMessage(
        "Assessment saved. Review findings before recording a decision.",
      );
    });
  }
  async function download(path, filename) {
    await perform(async () => {
      const blob = await api(path, {}, true);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  async function saveDecision() {
    await perform(async () => {
      const result = await api("/review/decision", {
        method: "POST",
        body: JSON.stringify({
          audit_id: audit.audit_id,
          action: decision,
          justification: reason,
        }),
      });
      applyAudit(result.results);
      setMessage(
        "Officer decision recorded separately from the automated assessment.",
      );
    });
  }
  async function saveOverride() {
    await perform(async () => {
      const result = await api("/audit/clause-override", {
        method: "POST",
        body: JSON.stringify({ audit_id: audit.audit_id, ...override }),
      });
      applyAudit(result.results);
      setMessage(
        "Override appended to the history; derived findings recalculated.",
      );
    });
  }

  return (
    <>
      <Head>
        <title>BidLens AI — Evidence-based bid review</title>
        <meta
          name="description"
          content="Tender-specific document review with explicit verification evidence and officer decisions."
        />
      </Head>
      <header className="top">
        <div>
          <span className="eyebrow">PROCUREMENT DECISION SUPPORT</span>
          <h1>
            BidLens AI<span> / Review workspace</span>
          </h1>
        </div>
        <a href="https://github.com/DEATH84169/BidLens-AI">
          Fork & documentation ↗
        </a>
      </header>
      <main>
        <section className="notice">
          <strong>Know what has been verified.</strong> Document claims,
          official responses and officer decisions are shown separately. An
          unavailable registry remains unverified. No automated qualification or
          disqualification.
        </section>
        <section className="panel connection">
          <div>
            <h2>Officer access</h2>
            <p>
              Use the pilot officer access key configured on your backend. It
              stays in this page’s memory; do not enter API Setu provider
              secrets here.
            </p>
          </div>
          <label>
            Officer access key
            <input
              type="password"
              autoComplete="off"
              value={accessKey}
              onChange={(e) => {
                setAccessKey(e.target.value);
                setConnected(false);
                setAudit(null);
                setHistory([]);
              }}
            />
          </label>
          <button onClick={connect} disabled={busy || !accessKey}>
            Connect
          </button>
        </section>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {message && (
          <div role="status" className="message">
            {message}
          </div>
        )}
        {busy && (
          <div role="status" className="message">
            Working… Scanned documents may take longer because every page is
            checked.
          </div>
        )}
        {connected && (
          <>
            <div className="workspace">
              <section className="panel">
                <div className="section-heading">
                  <span className="step">01</span>
                  <div>
                    <h2>Confirm the tender</h2>
                    <p>
                      Blank means unknown. Enter 0 only when no minimum applies.
                    </p>
                  </div>
                </div>
                <label className="upload">
                  Extract draft from RFP
                  <input
                    type="file"
                    accept=".pdf,.docx,.xlsx,.csv,.png,.jpg,.jpeg"
                    disabled={busy}
                    onChange={(e) => uploadTender(e.target.files[0])}
                  />
                </label>
                <div className="field-grid">
                  <label>
                    Tender reference
                    <input
                      value={tender.tender_id}
                      onChange={(e) =>
                        changeTender({ ...tender, tender_id: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Tender title
                    <input
                      value={tender.title}
                      onChange={(e) =>
                        changeTender({ ...tender, title: e.target.value })
                      }
                    />
                  </label>
                  {numericFields.map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <input
                        type="number"
                        min="0"
                        step="any"
                        max={key === "min_local_content_pct" ? 100 : undefined}
                        value={tender.requirements[key]}
                        onChange={(e) =>
                          changeTender({
                            ...tender,
                            requirements: {
                              ...tender.requirements,
                              [key]: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
                <fieldset>
                  <legend>Required registry / issuer checks</legend>
                  <div className="check-grid">
                    {checks.map((check) => (
                      <label className="checkbox" key={check.id}>
                        <input
                          type="checkbox"
                          checked={tender.required_checks.includes(check.id)}
                          onChange={(e) =>
                            changeTender({
                              ...tender,
                              required_checks: e.target.checked
                                ? [...tender.required_checks, check.id]
                                : tender.required_checks.filter(
                                    (c) => c !== check.id,
                                  ),
                            })
                          }
                        />
                        {check.name}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <label>
                  Scope confirmation and tender clause references
                  <textarea
                    value={tender.confirmation_note}
                    onChange={(e) =>
                      changeTender({
                        ...tender,
                        confirmation_note: e.target.value,
                      })
                    }
                    placeholder="Explain the applicable clauses, thresholds, and why any statutory checks are out of scope."
                  />
                </label>
                <button
                  disabled={busy || tender.confirmation_note.trim().length < 10}
                  onClick={confirmTender}
                >
                  Save confirmed tender version
                </button>
                {confirmedTender && (
                  <p className="success">
                    Saved version: {confirmedTender.version_id.slice(0, 8)}
                  </p>
                )}
              </section>
              <section className="panel">
                <div className="section-heading">
                  <span className="step">02</span>
                  <div>
                    <h2>Add one bidder’s evidence</h2>
                    <p>
                      Group the proposal and its supporting certificates in one
                      assessment.
                    </p>
                  </div>
                </div>
                <label className="upload">
                  Bidder attachments · 20 MB each
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.xlsx,.csv,.png,.jpg,.jpeg,.tiff,.bmp,.webp"
                    disabled={busy}
                    onChange={(e) => uploadBids(Array.from(e.target.files))}
                  />
                </label>
                <ul className="files">
                  {attachments.map((d) => (
                    <li key={d.file_id}>
                      <div>
                        <strong>{d.filename}</strong>
                        <small>SHA-256 {d.sha256.slice(0, 20)}…</small>
                      </div>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          setAttachments(
                            attachments.filter((a) => a.file_id !== d.file_id),
                          )
                        }
                      >
                        Remove from assessment
                      </button>
                    </li>
                  ))}
                </ul>
                {!attachments.length && (
                  <p className="empty">No evidence attached yet.</p>
                )}
                <label>
                  Verification environment
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="live">
                      Production sources — approval and credentials required
                    </option>
                    <option value="sandbox">
                      API Setu sandbox — test responses only
                    </option>
                    <option value="demo">
                      Local demonstration — no registry requests
                    </option>
                  </select>
                </label>
                {mode !== "live" && (
                  <p className="warning">
                    TEST MODE. Results cannot establish bidder eligibility.
                  </p>
                )}
                <button
                  disabled={
                    busy ||
                    !confirmedTender ||
                    !attachments.length ||
                    attachments.length > 20
                  }
                  onClick={runAudit}
                >
                  Evaluate this bidder
                </button>
                <p>
                  Provider credentials are configured on the server after
                  publisher approval. Without them, verification remains NOT
                  VERIFIED.
                </p>
                <div className="reference">
                  <h3>Public reference data</h3>
                  <p>
                    Selected MoSPI NIC 2008 divisions for interpreting older
                    certificates. A classification match does not verify Udyam
                    registration.
                  </p>
                  <label>
                    NIC 2008 division
                    <input
                      value={nicCode}
                      onChange={(e) => setNicCode(e.target.value)}
                    />
                  </label>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      perform(async () =>
                        setNic(
                          await api(
                            `/system/reference/nic2008/${encodeURIComponent(nicCode)}`,
                          ),
                        ),
                      )
                    }
                  >
                    Look up reference
                  </button>
                  {nic && (
                    <p>
                      {nic.description ||
                        "Not in the selected reference subset."}{" "}
                      <a href={nic.source_url} target="_blank" rel="noreferrer">
                        Official source ↗
                      </a>
                    </p>
                  )}
                </div>
              </section>
            </div>
            {audit && (
              <section className="panel assessment">
                <div className="section-heading">
                  <span className="step">03</span>
                  <div>
                    <h2>Review findings</h2>
                    <p>
                      {audit.tender.tender_id} · audit{" "}
                      {audit.audit_id.slice(0, 8)} · {audit.mode.toUpperCase()}
                    </p>
                  </div>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      download(
                        `/audit/report/pdf/${audit.audit_id}`,
                        `BidLens-${audit.audit_id}.pdf`,
                      )
                    }
                  >
                    Download evidence report
                  </button>
                </div>
                {audit.mode !== "live" && (
                  <div className="warning">
                    DEMONSTRATION / SANDBOX — No real bidder qualification may
                    be made from this assessment.
                  </div>
                )}
                <div className="metrics">
                  <div>
                    <span>Assessment</span>
                    <Badge value={audit.assessment_status} />
                  </div>
                  <div>
                    <span>Applicable checks passed</span>
                    <strong>
                      {audit.coverage.passed} / {audit.coverage.applicable}
                    </strong>
                  </div>
                  <div>
                    <span>Check coverage score</span>
                    <strong>
                      {audit.compliance_score ?? "—"}
                      {audit.compliance_score !== null ? "%" : ""}
                    </strong>
                    <small>Not a probability of compliance</small>
                  </div>
                  <div>
                    <span>Unresolved findings</span>
                    <strong>{audit.coverage.unresolved}</strong>
                  </div>
                </div>
                <p>{audit.executive_summary}</p>
                <p>
                  Risk level:{" "}
                  <Badge value={audit.rejection_risk_analysis.risk_tier} />
                </p>
                <h3>Source documents</h3>
                <ul className="files">
                  {audit.documents.map((d) => (
                    <li key={d.file_id}>
                      <span>{d.filename}</span>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          download(`/document/file/${d.file_id}`, d.filename)
                        }
                      >
                        Download original
                      </button>
                    </li>
                  ))}
                </ul>
                <h3>Tender checks</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Requirement</th>
                        <th>Finding</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.clause_level_decisions.map((clause) => (
                        <tr key={clause.clause_id}>
                          <td>{clause.clause_name}</td>
                          <td>
                            <Badge value={clause.status} />
                          </td>
                          <td>
                            {clause.evidence}
                            {clause.source_evidence?.map((e, i) => (
                              <blockquote key={i}>
                                {e.text}
                                <small>
                                  {e.filename} · page/sheet{" "}
                                  {e.page ?? "not available"}
                                </small>
                              </blockquote>
                            ))}
                            {clause.officer_override_note && (
                              <p>
                                <strong>Officer override:</strong>{" "}
                                {clause.officer_override_note}
                              </p>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h3>Registry and issuer checks</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Check</th>
                        <th>Status</th>
                        <th>Source evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.government_verification.gateways.map((g) => (
                        <tr key={g.id}>
                          <td>{g.name}</td>
                          <td>
                            <Badge value={g.status} />
                          </td>
                          <td>
                            {g.details.reason}
                            <small>
                              {g.details.source || "No source contacted"} ·{" "}
                              {g.details.checked_at || "No lookup timestamp"}
                            </small>
                            {g.details.response_sha256 && (
                              <small>
                                Response SHA-256: {g.details.response_sha256}
                              </small>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {audit.contradictions_detected.length > 0 && (
                  <>
                    <h3>Resolve evidence conflicts</h3>
                    {audit.contradictions_detected.map((c) => (
                      <div className="warning" key={c.contradiction_id}>
                        <strong>{c.title}</strong>
                        <p>{c.description}</p>
                        {c.source_evidence?.map((e, i) => (
                          <small key={i}>
                            {e.filename} · {e.text}
                          </small>
                        ))}
                      </div>
                    ))}
                  </>
                )}
                {audit.branch_a_extracted_data.unread_pages.map((p, i) => (
                  <div className="warning" key={i}>
                    Unread evidence: {p.filename}, page {p.page ?? "unknown"} —{" "}
                    {p.reason}
                  </div>
                ))}
                <div className="workspace review">
                  <div>
                    <h3>Justified clause override</h3>
                    <p>
                      Does not change registry verification. Original findings
                      remain in the saved snapshot.
                    </p>
                    <label>
                      Clause
                      <select
                        value={override.clause_id}
                        onChange={(e) =>
                          setOverride({
                            ...override,
                            clause_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Choose a clause</option>
                        {audit.clause_level_decisions.map((c) => (
                          <option key={c.clause_id} value={c.clause_id}>
                            {c.clause_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Officer finding
                      <select
                        value={override.new_status}
                        onChange={(e) =>
                          setOverride({
                            ...override,
                            new_status: e.target.value,
                          })
                        }
                      >
                        {[
                          "PENDING",
                          "PASS",
                          "FAIL",
                          "EXEMPT",
                          "NOT_APPLICABLE",
                        ].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Evidence and applicable clause
                      <textarea
                        value={override.justification}
                        onChange={(e) =>
                          setOverride({
                            ...override,
                            justification: e.target.value,
                          })
                        }
                      />
                    </label>
                    <button
                      disabled={
                        busy ||
                        !!audit.officer_decision ||
                        !override.clause_id ||
                        override.justification.trim().length < 10
                      }
                      onClick={saveOverride}
                    >
                      Record override
                    </button>
                  </div>
                  <div>
                    <h3>Procurement officer decision</h3>
                    <p>
                      Review unresolved checks and record your evidence basis.
                      AI findings are advisory.
                    </p>
                    <label>
                      Decision
                      <select
                        value={decision}
                        onChange={(e) => setDecision(e.target.value)}
                      >
                        <option value="REQUEST_CLARIFICATION">
                          Request clarification
                        </option>
                        <option
                          value="APPROVE"
                          disabled={audit.mode !== "live"}
                        >
                          Qualify bidder
                        </option>
                        <option value="REJECT" disabled={audit.mode !== "live"}>
                          Disqualify bidder
                        </option>
                      </select>
                    </label>
                    <label>
                      Decision justification
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    </label>
                    <button
                      disabled={
                        busy ||
                        reason.trim().length < 10 ||
                        (audit.mode !== "live" &&
                          decision !== "REQUEST_CLARIFICATION")
                      }
                      onClick={saveDecision}
                    >
                      Record officer decision
                    </button>
                    {audit.officer_decision && (
                      <p className="message">
                        Latest officer decision:{" "}
                        {audit.officer_decision.data.action}
                      </p>
                    )}
                  </div>
                </div>
                <details>
                  <summary>
                    Audit event history ({audit.history.length})
                  </summary>
                  <ol>
                    {audit.history.map((e) => (
                      <li key={e.id}>
                        <strong>{e.type}</strong> · {e.actor} ·{" "}
                        {new Date(e.timestamp).toLocaleString()}
                        <p>
                          {e.data.justification ||
                            "Evidence snapshot recorded."}
                        </p>
                        <small>Event hash: {e.event_hash}</small>
                      </li>
                    ))}
                  </ol>
                  <p>
                    Hash-linked local history detects changes to recorded
                    events. It is not independently anchored or immutable
                    storage.
                  </p>
                </details>
              </section>
            )}
            <section className="panel">
              <h2>Saved assessments</h2>
              <p>
                Each run preserves its own tender version and attachment hashes.
              </p>
              {history.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Bidder / tender</th>
                        <th>Created</th>
                        <th>Mode</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((h) => (
                        <tr key={h.audit_id}>
                          <td>
                            {h.vendor_name}
                            <small>{h.tender_id}</small>
                          </td>
                          <td>{new Date(h.created_at).toLocaleString()}</td>
                          <td>
                            <Badge value={h.mode} />
                          </td>
                          <td>
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() =>
                                perform(async () =>
                                  applyAudit(
                                    (await api(`/audit/status/${h.audit_id}`))
                                      .results,
                                  ),
                                )
                              }
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty">No saved assessments.</p>
              )}
            </section>
          </>
        )}
        <footer>
          BidLens AI · CPCL / GeM procurement prototype ·{" "}
          <a href="https://www.apisetu.gov.in/sop">API Setu onboarding</a>
          <p>
            Single-officer pilot. Use individual SSO accounts, role-based access
            and protected storage before a multi-user production deployment.
          </p>
        </footer>
      </main>
    </>
  );
}
