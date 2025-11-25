import requests
import json
import time
import sys
import uuid

# Configuration
BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_01.txt"

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
    # Clear output file
    with open(OUTPUT_FILE, "w") as f:
        f.write("=== Use Case 1: Brain Barrier Distribution (Single Individual) ===\n\n")

    log("Goal: Simulate a 30-year-old adult and measure drug concentration in the Brain vs Blood.")
    log("(Using Acetaminophen as a proxy compound)\n")
    
    # 1. Load Model
    log("[1] Loading Acetaminophen Pregnancy Model...")
    unique_id = f"sim_{uuid.uuid4().hex[:8]}"
    load_res = call_tool("load_simulation", {
        "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": unique_id
    }, critical=True)
    sim_id = load_res["simulationId"]
    log(f"    Model loaded. ID: {sim_id}")

    # 2. Configure Subject
    log("\n[2] Configuring Subject Parameters...")
    call_tool("set_parameter_value", {
        "simulationId": sim_id,
        "parameterPath": "Organism|Age",
        "value": 30.0,
        "unit": None
    }, critical=True)
    log("    Organism|Age set to 30.0 years.")

    # 3. Run Simulation
    log("\n[3] Running Simulation (Real Physics Engine)...")
    run_res = call_tool("run_simulation", {
        "simulationId": sim_id
    }, critical=True)
    job_id = run_res["jobId"]
    log(f"    Job submitted: {job_id}")

    # 4. Wait for Result
    log("\n[4] Waiting for completion...")
    result_id = None
    for _ in range(60):
        status_res = call_tool("get_job_status", {"jobId": job_id})
        status = status_res["job"]["status"]
        if status == "succeeded":
            result_id = status_res["job"]["resultId"]
            break
        elif status in ["failed", "cancelled"]:
            log(f"    Job failed: {status_res['job'].get('error')}")
            sys.exit(1)
        time.sleep(2)
    
    if not result_id:
        log("    Timeout.")
        sys.exit(1)

    # 5. Analyze Results
    log(f"\n[5] Analyzing Results (Result ID: {result_id})...")
    pk_res = call_tool("calculate_pk_parameters", {
        "simulationId": sim_id,
        "resultsId": result_id
    })
    
    log("\n=== PHARMACOKINETIC METRICS ===")
    brain_auc = 0.0
    
    for metric in pk_res.get("metrics", []):
        path = metric["parameter"]
        if "Brain|Intracellular" in path:
            log(f"BRAIN (Intracellular): Cmax={metric.get('cmax'):.2f} {metric.get('unit')}, AUC={metric.get('auc'):.2f}")
            brain_auc = metric.get('auc', 0)
        elif "ArterialBlood|Plasma" in path:
            log(f"BLOOD (Arterial):      Cmax={metric.get('cmax'):.2f} {metric.get('unit')}, AUC={metric.get('auc'):.2f}")

    if brain_auc > 0:
        log("\nConclusion: Drug successfully crosses the BBB in this simulation.")

if __name__ == "__main__":
    main()
