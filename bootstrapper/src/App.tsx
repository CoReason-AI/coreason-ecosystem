import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { openUrl } from "@tauri-apps/plugin-opener";
import "./App.css";

// ─── Schema Interfaces ────────────────────────────────────────────────────────

interface SwarmBootstrapReceipt {
  status: string;
  message: string;
  osType: string;
  dockerAvailable: boolean;
  dockerComposeAvailable: boolean;
  nemoclawInstalled: boolean;
  nemoclawOnboarded: boolean;
}

interface NemoClawInstallReceipt {
  status: string;
  message: string;
}

interface NemoClawOnboardReceipt {
  status: string;
  message: string;
}

interface SwarmIgnitionReceipt {
  status: string;
  message: string;
}

// ─── Boot State Machine ───────────────────────────────────────────────────────
// Idle → Detecting → InstallingNemoclaw → NeedNgcKey → OnboardingNemoclaw → Booting → Active
//                                                                                    ↘ Error (any step)

type BootState =
  | "Idle"
  | "Detecting"
  | "InstallingNemoclaw"
  | "NeedNgcKey"
  | "OnboardingNemoclaw"
  | "Booting"
  | "Active"
  | "Error";

// ─── Component ────────────────────────────────────────────────────────────────

function App() {
  const [bootState, setBootState] = useState<BootState>("Idle");
  const [receipt, setReceipt] = useState<SwarmBootstrapReceipt | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [logs, setLogs] = useState<string[]>([]);
  const [ngcApiKey, setNgcApiKey] = useState<string>("");
  const [ngcKeyError, setNgcKeyError] = useState<string>("");
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll log console
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Subscribe to streamed log events from Rust backend
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    listen<string>("boot-log", (event) => {
      setLogs((prev) => [...prev, event.payload]);
    }).then((fn) => {
      unlisten = fn;
    });
    return () => unlisten?.();
  }, []);

  // ─── Step 1: Dependency Detection ────────────────────────────────────────

  async function launchSwarm() {
    setBootState("Detecting");
    setLogs([]);
    setErrorMessage("");

    try {
      const depResult: SwarmBootstrapReceipt = await invoke("check_dependencies", {
        intent: { environmentMode: "local", includeDefaultKit: true },
      });
      setReceipt(depResult);

      if (depResult.status === "NEEDS_DOCKER") {
        setErrorMessage(depResult.message);
        setBootState("Error");
        return;
      }

      if (depResult.status === "NEEDS_NEMOCLAW_INSTALL") {
        setBootState("InstallingNemoclaw");
        await runNemoClawInstall();
        return;
      }

      if (depResult.status === "NEEDS_NEMOCLAW_ONBOARD") {
        setBootState("NeedNgcKey");
        return;
      }

      // All good — proceed to ignite
      setBootState("Booting");
      await runIgnition();
    } catch (error) {
      setErrorMessage(String(error));
      setBootState("Error");
    }
  }

  // ─── Step 2: Install NemoClaw Binary ─────────────────────────────────────

  async function runNemoClawInstall() {
    try {
      const result: NemoClawInstallReceipt = await invoke("install_nemoclaw");
      if (result.status === "SUCCESS") {
        // Binary is now installed; need NGC key to onboard
        setBootState("NeedNgcKey");
      } else {
        setErrorMessage(result.message);
        setBootState("Error");
      }
    } catch (error) {
      setErrorMessage(String(error));
      setBootState("Error");
    }
  }

  // ─── Step 3: Onboard NemoClaw with NGC API Key ────────────────────────────

  async function runOnboard() {
    if (!ngcApiKey.trim()) {
      setNgcKeyError("NGC API key is required.");
      return;
    }
    setNgcKeyError("");
    setBootState("OnboardingNemoclaw");

    try {
      const result: NemoClawOnboardReceipt = await invoke("onboard_nemoclaw", {
        intent: {
          ngcApiKey: ngcApiKey.trim(),
          sandboxName: "coreason",
        },
      });

      if (result.status === "SUCCESS") {
        setBootState("Booting");
        await runIgnition();
      } else {
        setErrorMessage(result.message);
        setBootState("Error");
      }
    } catch (error) {
      setErrorMessage(String(error));
      setBootState("Error");
    }
  }

  // ─── Step 4: Ignite Docker Swarm ─────────────────────────────────────────

  async function runIgnition() {
    try {
      const ignResult: SwarmIgnitionReceipt = await invoke("ignite_swarm", {
        intent: { forceRebuild: false },
      });

      if (ignResult.status === "SUCCESS") {
        setBootState("Active");
        // Refresh diagnostics state to show updated "Available" checkmarks
        try {
          const freshResult: SwarmBootstrapReceipt = await invoke("check_dependencies", {
            intent: { environmentMode: "local", includeDefaultKit: true },
          });
          setReceipt(freshResult);
        } catch (e) {
          console.error("Failed to refresh diagnostics", e);
        }
      } else {
        setErrorMessage(ignResult.message);
        setBootState("Error");
      }
    } catch (error) {
      setErrorMessage(String(error));
      setBootState("Error");
    }
  }

  async function openDashboard() {
    await openUrl("http://localhost:8080");
  }

  async function handleUninstall() {
    if (!window.confirm("Are you sure you want to completely uninstall NemoClaw and wipe all sandbox configuration?")) return;
    setBootState("Detecting");
    setLogs(["[Uninstall] Initiating wipe..."]);
    try {
      await invoke("uninstall_nemoclaw");
      setLogs((prev) => [...prev, "Uninstall complete. Restarting detection..."]);
      setTimeout(() => {
        launchSwarm();
      }, 1500);
    } catch (e) {
      setErrorMessage(String(e));
      setBootState("Error");
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  const isStreaming =
    bootState === "InstallingNemoclaw" ||
    bootState === "OnboardingNemoclaw" ||
    bootState === "Booting";

  return (
    <main style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>CoReason Swarm Ignition</h1>
        <p style={styles.subtitle}>Zero-to-Swarm in one click.</p>
      </div>

      {/* ── Step Indicator ── */}
      <StepIndicator bootState={bootState} />

      {/* ── IDLE: Launch button ── */}
      {bootState === "Idle" && (
        <div style={styles.card}>
          <p style={styles.cardText}>
            The bootstrapper will detect your environment, install any missing dependencies,
            and ignite the CoReason swarm automatically.
          </p>
          <button style={styles.primaryButton} onClick={launchSwarm}>
            🚀 Launch Swarm
          </button>
        </div>
      )}

      {/* ── DETECTING ── */}
      {bootState === "Detecting" && (
        <div style={styles.card}>
          <Spinner label="Scanning environment dependencies…" />
        </div>
      )}

      {/* ── INSTALLING NEMOCLAW ── */}
      {bootState === "InstallingNemoclaw" && (
        <div style={styles.card}>
          <Spinner label="Installing NemoClaw binary via NVIDIA installer…" />
          <LogConsole logs={logs} logsEndRef={logsEndRef} />
        </div>
      )}

      {/* ── NEED NGC KEY ── */}
      {bootState === "NeedNgcKey" && (
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>🔑 NGC API Key Required</h2>
          <p style={styles.cardText}>
            NemoClaw needs your NVIDIA NGC API key to configure the security sandbox.
            Your key is used only locally and is never stored or transmitted by CoReason.
          </p>
          <p style={styles.helpLink}>
            Get a free key at{" "}
            <span
              style={styles.link}
              onClick={() => openUrl("https://org.ngc.nvidia.com/setup/api-key")}
            >
              org.ngc.nvidia.com/setup/api-key
            </span>
          </p>

          <div style={styles.inputGroup}>
            <label style={styles.label} htmlFor="ngc-key-input">
              NGC API Key
            </label>
            <input
              id="ngc-key-input"
              type="password"
              value={ngcApiKey}
              onChange={(e) => setNgcApiKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runOnboard()}
              placeholder="nvapi-xxxxxxxxxxxxxxxxxxxx"
              style={{
                ...styles.input,
                borderColor: ngcKeyError ? "#f44336" : "#444",
              }}
            />
            {ngcKeyError && <p style={styles.fieldError}>{ngcKeyError}</p>}
          </div>

          <button style={styles.primaryButton} onClick={runOnboard}>
            Configure NemoClaw Sandbox
          </button>
        </div>
      )}

      {/* ── ONBOARDING ── */}
      {bootState === "OnboardingNemoclaw" && (
        <div style={styles.card}>
          <Spinner label="Configuring NemoClaw sandbox 'coreason'… (this may take 2–3 minutes)" />
          <LogConsole logs={logs} logsEndRef={logsEndRef} />
        </div>
      )}

      {/* ── BOOTING DOCKER SWARM ── */}
      {bootState === "Booting" && (
        <div style={styles.card}>
          <Spinner label="Igniting Docker swarm containers…" />
          <LogConsole logs={logs} logsEndRef={logsEndRef} />
        </div>
      )}

      {/* ── ACTIVE ── */}
      {bootState === "Active" && (
        <div style={{ ...styles.card, borderColor: "#4CAF50" }}>
          <h2 style={{ ...styles.cardTitle, color: "#4CAF50" }}>✅ Swarm is Active!</h2>
          <p style={styles.cardText}>
            All services are running. The Sensory Command Center is now online.
          </p>
          <button style={{ ...styles.primaryButton, background: "#4CAF50" }} onClick={openDashboard}>
            Open Sensory Command Center →
          </button>
        </div>
      )}

      {/* ── ERROR ── */}
      {bootState === "Error" && (
        <div style={{ ...styles.card, borderColor: "#f44336" }}>
          <h2 style={{ ...styles.cardTitle, color: "#f44336" }}>❌ Boot Failed</h2>
          <p style={styles.cardText}>{errorMessage}</p>
          <button style={{ ...styles.primaryButton, background: "#555" }} onClick={() => setBootState("Idle")}>
            Try Again
          </button>
        </div>
      )}

      {/* ── Streaming Log Console (shared during all streaming states) ── */}
      {isStreaming && logs.length === 0 && (
        <div style={styles.card}>
          <LogConsole logs={["Waiting for output…"]} logsEndRef={logsEndRef} />
        </div>
      )}

      {/* ── Diagnostics (after check, not in Idle) ── */}
      {receipt && bootState !== "Idle" && (
        <div style={styles.diagnostics}>
          <h3 style={{ margin: "0 0 0.5rem" }}>Environment Diagnostics</h3>
          <DiagRow label="OS" value={receipt.osType} />
          <DiagRow label="Docker Engine" ok={receipt.dockerAvailable} />
          <DiagRow label="Docker Compose" ok={receipt.dockerComposeAvailable} />
          <DiagRow label="NemoClaw Binary" ok={receipt.nemoclawInstalled} />
          <DiagRow label="NemoClaw Onboarded" ok={receipt.nemoclawOnboarded} />
          
          <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid #333", textAlign: "right" }}>
            <button 
              style={{ ...styles.secondaryButton, color: "#f44336", borderColor: "#f44336" }} 
              onClick={handleUninstall}
            >
              🗑️ Factory Reset (Uninstall)
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

// ─── Sub-Components ───────────────────────────────────────────────────────────

function StepIndicator({ bootState }: { bootState: BootState }) {
  const steps = [
    { id: "Detecting", label: "Detect" },
    { id: "InstallingNemoclaw", label: "Install" },
    { id: "NeedNgcKey", label: "Configure" },
    { id: "OnboardingNemoclaw", label: "Onboard" },
    { id: "Booting", label: "Ignite" },
    { id: "Active", label: "Active" },
  ];

  const order = steps.map((s) => s.id);
  const currentIdx = order.indexOf(bootState);

  return (
    <div style={styles.stepRow}>
      {steps.map((step, i) => {
        const done = currentIdx > i;
        const active = currentIdx === i;
        return (
          <div key={step.id} style={styles.stepItem}>
            <div
              style={{
                ...styles.stepDot,
                background: done ? "#4CAF50" : active ? "#f57c00" : "#444",
              }}
            >
              {done ? "✓" : i + 1}
            </div>
            <span style={{ fontSize: "0.7rem", color: active ? "#f57c00" : "#888" }}>
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Spinner({ label }: { label: string }) {
  return (
    <div style={styles.spinnerRow}>
      <span style={styles.spinner} />
      <span style={{ color: "#ccc" }}>{label}</span>
    </div>
  );
}

function LogConsole({
  logs,
  logsEndRef,
}: {
  logs: string[];
  logsEndRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div style={styles.logConsole}>
      {logs.map((log, i) => (
        <div key={i} style={{ lineHeight: "1.5" }}>
          {log}
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  );
}

function DiagRow({ label, ok, value }: { label: string; ok?: boolean; value?: string }) {
  return (
    <div style={{ display: "flex", gap: "0.5rem", padding: "2px 0" }}>
      <span style={{ color: "#888", minWidth: "180px" }}>{label}:</span>
      <span style={{ color: ok === undefined ? "#ccc" : ok ? "#4CAF50" : "#f44336" }}>
        {value ?? (ok ? "✅ Available" : "❌ Missing")}
      </span>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    background: "#121212",
    color: "#e0e0e0",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    padding: "2rem",
    maxWidth: "680px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem",
  },
  header: {
    textAlign: "center",
    paddingBottom: "0.5rem",
    borderBottom: "1px solid #333",
  },
  title: {
    margin: 0,
    fontSize: "1.8rem",
    fontWeight: 700,
    background: "linear-gradient(90deg, #f57c00, #ff9800)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  subtitle: {
    margin: "0.25rem 0 0",
    color: "#888",
    fontSize: "0.95rem",
  },
  card: {
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: "10px",
    padding: "1.5rem",
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },
  cardTitle: {
    margin: 0,
    fontSize: "1.2rem",
  },
  cardText: {
    margin: 0,
    color: "#aaa",
    lineHeight: "1.6",
    fontSize: "0.95rem",
  },
  primaryButton: {
    padding: "12px 24px",
    fontSize: "1rem",
    fontWeight: 600,
    cursor: "pointer",
    background: "#f57c00",
    color: "white",
    border: "none",
    borderRadius: "6px",
    transition: "opacity 0.2s",
    alignSelf: "flex-start",
  },
  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "0.4rem",
  },
  label: {
    fontSize: "0.85rem",
    color: "#bbb",
    fontWeight: 500,
  },
  input: {
    padding: "10px 14px",
    fontSize: "0.95rem",
    background: "#2a2a2a",
    color: "#e0e0e0",
    border: "1px solid #444",
    borderRadius: "6px",
    outline: "none",
    fontFamily: "monospace",
    letterSpacing: "0.05em",
  },
  fieldError: {
    margin: 0,
    fontSize: "0.8rem",
    color: "#f44336",
  },
  helpLink: {
    margin: 0,
    fontSize: "0.85rem",
    color: "#888",
  },
  link: {
    color: "#f57c00",
    cursor: "pointer",
    textDecoration: "underline",
  },
  logConsole: {
    background: "#0d0d0d",
    color: "#00e676",
    fontFamily: "monospace",
    fontSize: "0.78rem",
    padding: "1rem",
    borderRadius: "6px",
    height: "180px",
    overflowY: "auto",
    lineHeight: "1.4",
    border: "1px solid #222",
  },
  stepRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "0.5rem 0",
  },
  stepItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "4px",
    flex: 1,
  },
  stepDot: {
    width: "28px",
    height: "28px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.75rem",
    fontWeight: 700,
    color: "white",
    transition: "background 0.3s",
  },
  spinnerRow: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
  },
  spinner: {
    display: "inline-block",
    width: "18px",
    height: "18px",
    border: "2px solid #444",
    borderTopColor: "#f57c00",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  diagnostics: {
    background: "#1a1a1a",
    border: "1px solid #2a2a2a",
    borderRadius: "8px",
    padding: "1rem 1.25rem",
    fontSize: "0.85rem",
  },
};

export default App;
