import requests
import json
import time
import sys
import uuid

# Configuration
BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_06.txt"

def log(msg):
    print(msg)
    with open(OUTPUT_FILE, "a") as f:
        f.write(msg + "\n")

def call_tool(name, args, critical=False):
    payload = {
        "tool": name,
        "arguments": args,
        "critical": critical
    }
    response = requests.post(BASE_URL, json=payload, headers=HEADERS)
    if response.status_code != 200:
        log(f"Error calling {name}: {response.text}")
        sys.exit(1)
    return response.json()["structuredContent"]

def main():
    with open(OUTPUT_FILE, "w") as f:
        f.write("=== Use Case 6: Automated Sensitivity Analysis Tool ===\n\n")

    log("Goal: Use the 'run_sensitivity_analysis' tool to automatically sweep Liver Volume.")
    
    # 1. Run Tool
    log("[1] Submitting Job...")
    
    # Reduce deltas to 1 to test speed, or assume it's fast
    req = {
        "modelPath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": f"sens_tool_{uuid.uuid4().hex[:4]}",
        "parameters": [
            {
                "path": "Organism|Liver|Volume",
                "baselineValue": 1.5,
                "deltas": [-0.5, 1.0], # Reduced set: 0.75, 3.0
                "unit": "l"
            }
        ],
        "pollIntervalSeconds": 1.0,
        "jobTimeoutSeconds": 120.0 # 2 minutes max
    }
    
    start = time.time()
    res = call_tool("run_sensitivity_analysis", req, critical=True)
    duration = time.time() - start
    
    log(f"\n[2] Analysis Complete ({duration:.1f}s)!")
    report = res["report"]
    csv_data = res["csv"]
    
    log(f"\nGenerated CSV: {csv_data['filename']} ({len(csv_data['data'])} bytes)")
    
    log("\n=== REPORT SCENARIOS ===")
    for scenario in report["scenarios"]:
        vol = scenario["absolute_value"]
        vol_str = f"{vol:.2f}" if vol is not None else "Baseline"
        status = scenario["job_status"]
        log(f"\nScenario: Liver Volume = {vol_str} L (Status: {status})")
        
        if status == "succeeded":
            found = False
            for m in scenario.get("metrics", []):
                if "Brain|Intracellular" in m["parameter"]:
                    log(f"  Brain AUC: {m.get('auc'):.2f}")
                    found = True
            if not found:
                log("  (No Brain metric found in output)")
        else:
            log(f"  Error: {scenario.get('error')}")

if __name__ == "__main__":
    main()
