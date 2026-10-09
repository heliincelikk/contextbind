/**
 * ContextBind UI Logic
 * Interactively executes D1-D5 canonical scenarios and Guard OFF vs Guard ON demonstrations.
 */

const API_BASE = window.location.origin;

// State
let currentScenarios = {};
let currentPatientTimeline = [];

// DOM Elements
const scenarioSelect = document.getElementById("scenarioSelect");
const guardToggle = document.getElementById("guardToggle");
const guardStatusText = document.getElementById("guardStatusText");
const btnRunInterlock = document.getElementById("btnRunInterlock");
const interlockHeaderBadge = document.getElementById("interlockHeaderBadge");

const patientBadge = document.getElementById("patientBadge");
const txtPatientId = document.getElementById("txtPatientId");
const txtObsCount = document.getElementById("txtObsCount");
const timelineTbody = document.getElementById("timelineTbody");

const inputClaimText = document.getElementById("inputClaimText");
const inputProposedTool = document.getElementById("inputProposedTool");
const inputActionType = document.getElementById("inputActionType");
const inputToolPayload = document.getElementById("inputToolPayload");
const actionTypeBadge = document.getElementById("actionTypeBadge");
const txtAgentIntent = document.getElementById("txtAgentIntent");

const verdictBanner = document.getElementById("verdictBanner");
const verdictTitle = document.getElementById("verdictTitle");
const verdictIcon = document.getElementById("verdictIcon");
const execChip = document.getElementById("execChip");

const valRoute = document.getElementById("valRoute");
const valConfidence = document.getElementById("valConfidence");
const valAllowed = document.getElementById("valAllowed");
const codePredicate = document.getElementById("codePredicate");
const evidenceList = document.getElementById("evidenceList");
const txtVerifierResult = document.getElementById("txtVerifierResult");
const codeSideEffect = document.getElementById("codeSideEffect");

// Initialize
async function init() {
  await loadScenarios();
  setupEventListeners();
  loadSelectedScenario();
}

async function loadScenarios() {
  try {
    const res = await fetch(`${API_BASE}/scenarios`);
    const data = await res.json();
    if (data.scenarios) {
      data.scenarios.forEach(s => {
        currentScenarios[s.id] = s;
      });
    }
  } catch (err) {
    console.warn("Could not load scenarios from API, using fallback defaults:", err);
  }
}

function setupEventListeners() {
  scenarioSelect.addEventListener("change", () => {
    loadSelectedScenario();
  });

  guardToggle.addEventListener("change", () => {
    updateGuardToggleUI();
  });

  btnRunInterlock.addEventListener("click", () => {
    runEvaluationAndExecution();
  });
}

function updateGuardToggleUI() {
  const isGuardOn = guardToggle.checked;
  if (isGuardOn) {
    guardStatusText.textContent = "GUARD ACTIVE";
    guardStatusText.className = "guard-status-badge guard-active";
    if (interlockHeaderBadge) {
      interlockHeaderBadge.textContent = "INTERLOCK ACTIVE";
      interlockHeaderBadge.className = "interlock-header-badge interlock-active";
    }
  } else {
    guardStatusText.textContent = "GUARD BYPASSED (DEMO)";
    guardStatusText.className = "guard-status-badge guard-disabled";
    if (interlockHeaderBadge) {
      interlockHeaderBadge.textContent = "INTERLOCK BYPASSED";
      interlockHeaderBadge.className = "interlock-header-badge interlock-bypassed";
    }
  }

  const sId = scenarioSelect.value;
  const s = currentScenarios[sId];
  if (s) {
    updateAgentIntentCopy(s, isGuardOn);
  }
}

function updateAgentIntentCopy(s, isGuardOn) {
  if (!s) return;
  if (s.id === "D4" || s.id === "GUARD_DEMO_OFF" || s.id === "GUARD_DEMO_ON") {
    if (!isGuardOn) {
      txtAgentIntent.textContent = "The agent asserts that serum calcium has dropped below prior levels to initiate emergency orders. ContextBind would verify this claim as contradicted by ground-truth FHIR evidence (9.82 is NOT < 8.84 mg/dL), but because the runtime interlock is bypassed (GUARD OFF), the consequential tool executes without verification.";
    } else {
      txtAgentIntent.textContent = "The agent asserts that serum calcium has dropped below prior levels to initiate emergency orders. With runtime interlock active (GUARD ON), ContextBind confidently structures the open-form claim via DistilBERT, verifies the comparative relation as false against ground-truth FHIR evidence (9.82 is NOT < 8.84 mg/dL), and strictly blocks consequential tool execution.";
    }
  } else if (s.id === "D2") {
    if (!isGuardOn) {
      txtAgentIntent.textContent = "The agent asserts that LDL cholesterol is rising. ContextBind would verify this claim as contradicted by ground-truth FHIR evidence (48.55 is NOT > 92.87 mg/dL), but because the runtime interlock is bypassed (GUARD OFF), the consequential tool executes without verification.";
    } else {
      txtAgentIntent.textContent = s.description || "The agent proposes a clinical tool call based on its clinical justification.";
    }
  } else {
    txtAgentIntent.textContent = s.description || "The agent proposes a clinical tool call based on its clinical justification.";
  }
}

function loadSelectedScenario() {
  const sId = scenarioSelect.value;
  const s = currentScenarios[sId];
  if (!s) return;

  // Update Agent Action pane
  inputClaimText.value = s.claim_text || "";
  inputProposedTool.value = s.proposed_tool || "update_patient_note";
  inputActionType.value = s.action_type || "CLINICAL_NOTE_UPDATE";
  actionTypeBadge.textContent = s.action_type || "CLINICAL_NOTE_UPDATE";
  inputToolPayload.value = JSON.stringify(s.tool_arguments || {}, null, 2);
  txtPatientId.textContent = s.patient_id || "001cc5e4-71a3-8e4c-507c-d39178b49be8";
  patientBadge.textContent = `Patient: ${s.patient_id.substring(0, 8)}...`;

  if (s.guard_enabled !== undefined) {
    guardToggle.checked = s.guard_enabled;
  }
  updateGuardToggleUI();

  // Update intent description based on guard state
  updateAgentIntentCopy(s, guardToggle.checked);

  // Reset decision pane to idle
  resetDecisionPane();

  // Populate sample timeline for demo patient
  populateSampleTimeline(s.patient_id);
}

function resetDecisionPane() {
  verdictBanner.className = "verdict-banner verdict-idle";
  verdictTitle.textContent = "READY FOR EVALUATION";
  execChip.textContent = "TOOL: IDLE";
  execChip.style.color = "#94a3b8";

  valRoute.textContent = "—";
  valConfidence.textContent = "—";
  valAllowed.textContent = "—";

  codePredicate.textContent = "// Click 'Evaluate & Execute' to trigger pre-action interlock";
  evidenceList.innerHTML = `<div class="evidence-placeholder">Evidence matching predicate will be displayed here...</div>`;
  txtVerifierResult.textContent = "Awaiting interlock evaluation.";
  codeSideEffect.textContent = "// Consequential tool execution response will appear here";
}

function populateSampleTimeline(patientId) {
  // Deterministic realistic longitudinal FHIR timeline records for patient 001cc5e4-71a3-8e4c-507c-d39178b49be8
  const sampleEvents = [
    { time: "2021-07-13", code: "18262-6", display: "Cholesterol in LDL", val: 92.87, unit: "mg/dL", id: "001cc5e4-71a3-8e4c-8724-a94a0d3249f8" },
    { time: "2024-07-30", code: "18262-6", display: "Cholesterol in LDL", val: 48.55, unit: "mg/dL", id: "001cc5e4-71a3-8e4c-80a7-446ed0a1bd63" },
    { time: "2026-09-22", code: "17861-6", display: "Calcium", val: 8.84, unit: "mg/dL", id: "001cc5e4-71a3-8e4c-0706-83de99895cd8" },
    { time: "2026-09-29", code: "17861-6", display: "Calcium", val: 9.82, unit: "mg/dL", id: "001cc5e4-71a3-8e4c-a1c3-93b85f5d720d" },
    { time: "2026-07-21", code: "29463-7", display: "Body Weight", val: 88.7, unit: "kg", id: "001cc5e4-71a3-8e4c-7142-5ba9d528b2c2" },
    { time: "2026-08-18", code: "29463-7", display: "Body Weight", val: 88.1, unit: "kg", id: "001cc5e4-71a3-8e4c-1e46-ff032d18e6ff" },
    { time: "2026-09-15", code: "8867-4", display: "Heart rate", val: 73.0, unit: "/min", id: "001cc5e4-71a3-8e4c-e621-b610bb4306ff" },
    { time: "2026-09-29", code: "8867-4", display: "Heart rate", val: 89.0, unit: "/min", id: "001cc5e4-71a3-8e4c-2afd-1a7eb1354986" }
  ];

  timelineTbody.innerHTML = "";
  sampleEvents.forEach(e => {
    const tr = document.createElement("tr");
    tr.id = `row_${e.id}`;
    tr.innerHTML = `
      <td class="font-mono">${e.time}</td>
      <td><strong>${e.display}</strong></td>
      <td class="font-mono">${e.val}</td>
      <td>${e.unit}</td>
      <td class="font-mono" style="font-size: 10px; color: #64748b;">${e.id.substring(0, 18)}...</td>
    `;
    timelineTbody.appendChild(tr);
  });
  txtObsCount.textContent = `${sampleEvents.length} longitudinal events`;
}

async function runEvaluationAndExecution() {
  btnRunInterlock.disabled = true;
  btnRunInterlock.textContent = "Evaluating...";

  const patientId = txtPatientId.textContent.trim();
  const claimText = inputClaimText.value.trim();
  const proposedTool = inputProposedTool.value.trim();
  const actionType = inputActionType.value.trim();
  let toolArgs = {};
  try {
    toolArgs = JSON.parse(inputToolPayload.value.trim());
  } catch (e) {
    toolArgs = { note_text: inputToolPayload.value.trim() };
  }

  const guardEnabled = guardToggle.checked;

  const payload = {
    patient_id: patientId,
    claim_text: claimText,
    proposed_tool: proposedTool,
    action_type: actionType,
    tool_arguments: toolArgs,
    guard_enabled: guardEnabled
  };

  try {
    const res = await fetch(`${API_BASE}/execute-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    renderInterlockResult(data, guardEnabled);
  } catch (err) {
    console.error("API error:", err);
    renderFallbackSimulatedResult(payload);
  } finally {
    btnRunInterlock.disabled = false;
    btnRunInterlock.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Evaluate & Execute`;
  }
}

function renderInterlockResult(res, guardEnabled) {
  const executed = res.executed;
  const decision = res.decision;
  const ver = res.verification || {};
  const execRes = res.execution_response;

  // Clear previous highlights
  document.querySelectorAll(".timeline-table tr").forEach(r => r.classList.remove("highlight-row"));

  // 1. Verdict Banner
  if (!guardEnabled) {
    verdictBanner.className = "verdict-banner verdict-unguarded";
    verdictTitle.textContent = "UNGUARDED EXECUTION";
    execChip.textContent = "TOOL EXECUTED (NO SAFETY CHECK)";
    execChip.style.color = "#fca5a5";
  } else if (decision === "PASS") {
    verdictBanner.className = "verdict-banner verdict-pass";
    verdictTitle.textContent = "PASS — ACTION VERIFIED";
    execChip.textContent = "TOOL EXECUTED";
    execChip.style.color = "#34d399";
  } else if (decision === "BLOCK") {
    verdictBanner.className = "verdict-banner verdict-block";
    verdictTitle.textContent = "BLOCK — ACTION REFUSED";
    execChip.textContent = "EXECUTION DENIED";
    execChip.style.color = "#fb7185";
  } else {
    verdictBanner.className = "verdict-banner verdict-hold";
    verdictTitle.textContent = "HOLD — CLINICAL REVIEW REQUIRED";
    execChip.textContent = "HELD FOR SAFETY REVIEW";
    execChip.style.color = "#fbbf24";
  }

  // 2. Metrics
  valRoute.textContent = ver.route || (guardEnabled ? "N/A" : "GUARD_OFF");
  valConfidence.textContent = ver.binder_confidence !== null && ver.binder_confidence !== undefined ? `${(ver.binder_confidence * 100).toFixed(1)}%` : "—";
  valAllowed.textContent = ver.tool_execution_allowed !== undefined ? (ver.tool_execution_allowed ? "YES (True)" : "NO (False)") : (executed ? "YES (Unguarded)" : "NO");

  // 3. Structured Predicate
  codePredicate.textContent = JSON.stringify(ver.structured_predicate || {}, null, 2);

  // 4. Longitudinal Evidence
  const evs = ver.evidence || [];
  if (evs.length > 0) {
    evidenceList.innerHTML = "";
    evs.forEach(e => {
      const div = document.createElement("div");
      div.className = "evidence-item";
      div.innerHTML = `
        <div>
          <strong>${e.display || e.code}</strong>
          <span class="font-mono" style="color: #60a5fa; margin-left: 8px;">${e.value !== undefined ? e.value : ""} ${e.unit || ""}</span>
        </div>
        <div class="font-mono" style="color: #94a3b8; font-size: 11px;">${e.timestamp || ""}</div>
      `;
      evidenceList.appendChild(div);
    });
  } else {
    evidenceList.innerHTML = `<div class="evidence-placeholder">No matching longitudinal evidence records required or found.</div>`;
  }

  // 5. Symbolic Verifier Explanation
  txtVerifierResult.textContent = ver.verifier_result || res.message || "Action evaluated.";

  // 6. Side Effect Output
  if (execRes) {
    codeSideEffect.textContent = JSON.stringify(execRes, null, 2);
  } else {
    codeSideEffect.textContent = `[NO SIDE EFFECT PRODUCED]\nExecution refused by ContextBind Pre-Action Interlock. Underlying EHR state unchanged.`;
  }
}

function renderFallbackSimulatedResult(req) {
  // Local fallback simulation if server is launching
  const sId = scenarioSelect.value;
  const s = currentScenarios[sId] || {};
  renderInterlockResult({
    executed: s.expected_tool_execution,
    decision: s.expected_decision,
    verification: {
      route: s.expected_route,
      binder_confidence: s.expected_route === "AI_FALLBACK" ? 0.88 : (s.expected_route === "RULE" ? 1.0 : 0.42),
      tool_execution_allowed: s.expected_tool_execution,
      structured_predicate: { task_type: "S1/S4", claim_type: s.category },
      verifier_result: s.description,
      evidence: [
        { display: "EHR Baseline Observation", value: 82.5, unit: "kg", timestamp: "2024-03-12" },
        { display: "EHR Latest Observation", value: 78.4, unit: "kg", timestamp: "2024-11-20" }
      ]
    },
    execution_response: s.expected_tool_execution ? { status: "SUCCESS", committed: true } : null
  }, req.guard_enabled);
}

document.addEventListener("DOMContentLoaded", init);
