import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { openUrl } from "@tauri-apps/plugin-opener";
import "./App.css";

interface SwarmBootstrapReceipt {
  status: string;
  message: string;
  osType: string;
  dockerAvailable: boolean;
  dockerComposeAvailable: boolean;
  nemoclawAvailable: boolean;
}

interface SwarmIgnitionReceipt {
  status: string;
  message: string;
}

type BootState = "Idle" | "Detecting" | "Booting" | "Active" | "Error";

function App() {
  const [bootState, setBootState] = useState<BootState>("Idle");
  const [receipt, setReceipt] = useState<SwarmBootstrapReceipt | null>(null);
  const [ignitionReceipt, setIgnitionReceipt] = useState<SwarmIgnitionReceipt | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  useEffect(() => {
    const setupListener = async () => {
      const unlisten = await listen<string>("boot-log", (event) => {
        setLogs((prev) => [...prev, event.payload]);
      });
      return unlisten;
    };

    let unlistenFn: () => void;
    setupListener().then((fn) => {
      unlistenFn = fn;
    });

    return () => {
      if (unlistenFn) {
        unlistenFn();
      }
    };
  }, []);

  async function launchSwarm() {
    setBootState("Detecting");
    try {
      // 1. Dependency Check
      const depResult: SwarmBootstrapReceipt = await invoke("check_dependencies", {
        intent: {
          environmentMode: "local",
          includeDefaultKit: true,
        },
      });
      setReceipt(depResult);

      if (depResult.status !== "SUCCESS") {
        setBootState("Error");
        return;
      }

      // 2. Ignite Swarm
      setBootState("Booting");
      const ignResult: SwarmIgnitionReceipt = await invoke("ignite_swarm", {
        intent: {
          forceRebuild: false,
        },
      });
      setIgnitionReceipt(ignResult);

      if (ignResult.status === "SUCCESS") {
        setBootState("Active");
      } else {
        setBootState("Error");
      }

    } catch (error) {
      console.error(error);
      setBootState("Error");
    }
  }

  async function openDashboard() {
    // Open in user's default browser using Tauri's opener plugin
    await openUrl("http://localhost:8080");
  }

  return (
    <main className="container" style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>CoReason Swarm Ignition</h1>
      <p>Zero-to-Swarm in 1 Click.</p>

      {bootState === "Idle" && (
        <button 
          onClick={launchSwarm} 
          style={{ padding: "12px 24px", fontSize: "16px", cursor: "pointer", background: "#f57c00", color: "white", border: "none", borderRadius: "4px" }}
        >
          Launch Swarm
        </button>
      )}

      {bootState === "Detecting" && <p>Checking environment dependencies...</p>}
      {bootState === "Booting" && (
        <div style={{ marginTop: "1rem" }}>
          <p>Booting up containers (this may take a minute on first run)...</p>
          <div style={{ 
            marginTop: "1rem", 
            background: "#1e1e1e", 
            color: "#00ff00", 
            fontFamily: "monospace", 
            padding: "1rem", 
            borderRadius: "8px", 
            height: "200px", 
            overflowY: "auto",
            textAlign: "left",
            fontSize: "12px",
            boxShadow: "inset 0 0 10px rgba(0,0,0,0.5)"
          }}>
            {logs.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
      
      {bootState === "Active" && (
        <div style={{ marginTop: "2rem", padding: "1.5rem", border: "2px solid #4CAF50", borderRadius: "8px" }}>
          <h2>✅ Swarm is Active!</h2>
          <p>{ignitionReceipt?.message}</p>
          <button 
            onClick={openDashboard}
            style={{ padding: "10px 20px", fontSize: "16px", cursor: "pointer", background: "#4CAF50", color: "white", border: "none", borderRadius: "4px" }}
          >
            Open Sensory Command Center
          </button>
        </div>
      )}

      {bootState === "Error" && (
        <div style={{ marginTop: "2rem", padding: "1rem", border: "2px solid #f44336", borderRadius: "8px", color: "#f44336" }}>
          <h2>❌ Boot Failed</h2>
          {receipt && receipt.status !== "SUCCESS" && <p>{receipt.message}</p>}
          {ignitionReceipt && ignitionReceipt.status !== "SUCCESS" && <p>{ignitionReceipt.message}</p>}
        </div>
      )}

      {receipt && bootState !== "Idle" && bootState !== "Active" && (
        <div style={{ marginTop: "2rem", textAlign: "left", background: "#242424", padding: "1rem", borderRadius: "8px", fontSize: "0.9em", color: "#ccc" }}>
          <h3>Diagnostic Info</h3>
          <ul>
            <li><strong>OS:</strong> {receipt.osType}</li>
            <li><strong>Docker Engine:</strong> {receipt.dockerAvailable ? "✅" : "❌"}</li>
            <li><strong>Docker Compose:</strong> {receipt.dockerComposeAvailable ? "✅" : "❌"}</li>
            <li><strong>NemoClaw Proxy:</strong> {receipt.nemoclawAvailable ? "✅" : "❌"}</li>
          </ul>
        </div>
      )}
    </main>
  );
}

export default App;
