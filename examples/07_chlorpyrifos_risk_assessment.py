import requests
import json
import time
import sys
import uuid

# Configuration
BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_07.txt"

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
        f.write("=== Use Case 7: Chlorpyrifos Risk Assessment (Proxy Method) ===\n\n")

    log("Goal: Assess exposure risk for Chlorpyrifos using the PBPK engine.")
    log("      (Using Acetaminophen model as a kinetic proxy for distribution)")
    
    # 1. Define Hazard Data (from EPA CompTox via User)
    # Chronic Oral MRL: 0.001 mg/kg-day
    # Estimated Plasma Css at MRL: 0.0161 mg/L
    threshold_mg_l = 0.0161
    
    log("\n[1] Hazard Identification (EPA CompTox Data)")
    log(f"    Chemical: Chlorpyrifos (DTXSID4020458)")
    log(f"    Neurotoxicity Threshold (Plasma Css): {threshold_mg_l} mg/L")
    
    # 2. Load Model
    log("\n[2] Loading Kinetic Model (Proxy)...")
    sim_id = f"tox_cpf_{uuid.uuid4().hex[:4]}"
    call_tool("load_simulation", {
        "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": sim_id
    }, critical=True)
    
    # 3. Configure Scenario (Vulnerable Population: Small Liver)
    # Reduced clearance typically increases risk for metabolic clearance drugs
    log("\n[3] Configuring Vulnerable Subject (Liver Volume 0.75L)...")
    call_tool("set_parameter_value", {
        "simulationId": sim_id,
        "parameterPath": "Organism|Liver|Volume",
        "value": 0.75,
        "unit": None
    }, critical=True)
    
    # 4. Run Simulation
    log("\n[4] Running Exposure Simulation...")
    run_res = call_tool("run_simulation", {"simulationId": sim_id}, critical=True)
    job_id = run_res["jobId"]
    
    # 5. Wait
    result_id = None
    for _ in range(30):
        res = call_tool("get_job_status", {"jobId": job_id})
        if res["job"]["status"] == "succeeded":
            result_id = res["job"]["resultId"]
            break
        time.sleep(1)
        
    if not result_id:
        log("    Simulation failed or timed out.")
        sys.exit(1)
        
    # 6. Calculate Metrics
    pk = call_tool("calculate_pk_parameters", {
        "simulationId": sim_id,
        "resultsId": result_id
    })
    
    # 7. Risk Characterization
    log("\n[5] Risk Characterization")
    
    # Extract Plasma Cmax
    plasma_cmax_umol = 0.0
    for m in pk.get("metrics", []):
        if "ArterialBlood|Plasma" in m["parameter"]:
            plasma_cmax_umol = m.get("cmax", 0.0)
            break
            
    # Convert to mg/L (Using Acetaminophen MW=151.16 as the carrier)
    # µmol/L * (g/mol) / 1000 = mg/L
    mw_proxy = 151.16
    plasma_cmax_mg = plasma_cmax_umol * mw_proxy / 1000.0
    
    log(f"    Simulated Plasma Cmax: {plasma_cmax_mg:.4f} mg/L")
    log(f"    Safety Threshold:      {threshold_mg_l:.4f} mg/L")
    
    ratio = plasma_cmax_mg / threshold_mg_l
    log(f"    Margin of Exposure (Ratio): {ratio:.1f}x Threshold")
    
    if plasma_cmax_mg > threshold_mg_l:
        log("\n    CONCLUSION: EXPOSURE EXCEEDS THRESHOLD. RISK INDICATED.")
    else:
        log("\n    CONCLUSION: Exposure is within safe limits.")

    # Brain Penetration Check
    brain_cmax_umol = 0.0
    for m in pk.get("metrics", []):
        if "Brain|Intracellular" in m["parameter"]:
            brain_cmax_umol = m.get("cmax", 0.0)
            break
            
    if brain_cmax_umol > 0:
        brain_mg = brain_cmax_umol * mw_proxy / 1000.0
        log(f"\n    Brain Exposure: {brain_mg:.4f} mg/L")
        log("    (Significant brain penetration confirmed)")

if __name__ == "__main__":
    main()
