import requests
import json
import time
import sys
import uuid

# Configuration
BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_02.txt"

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

def run_scenario(age):
    sim_id = f"age_{age}_{uuid.uuid4().hex[:4]}"
    log(f"\nRunning Scenario: Age={age} years...")
    
    # Load
    call_tool("load_simulation", {
        "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": sim_id
    }, critical=True)
    
    # Set Age
    call_tool("set_parameter_value", {
        "simulationId": sim_id,
        "parameterPath": "Organism|Age",
        "value": float(age),
        "unit": None
    }, critical=True)
    
    # Run
    run_res = call_tool("run_simulation", {"simulationId": sim_id}, critical=True)
    job_id = run_res["jobId"]
    
    # Wait
    result_id = None
    for _ in range(30):
        status_res = call_tool("get_job_status", {"jobId": job_id})
        status = status_res["job"]["status"]
        if status == "succeeded":
            result_id = status_res["job"]["resultId"]
            break
        elif status in ["failed", "cancelled"]:
            log(f"  Failed: {status_res['job'].get('error')}")
            return None
        time.sleep(1)
        
    if not result_id:
        log("  Timeout")
        return None
        
    # Get Metrics
    pk = call_tool("calculate_pk_parameters", {
        "simulationId": sim_id,
        "resultsId": result_id
    })
    
    # Extract Brain Cmax
    for m in pk.get("metrics", []):
        if "Brain|Intracellular" in m["parameter"]:
            return m
    return None

def main():
    with open(OUTPUT_FILE, "w") as f:
        f.write("=== Use Case 2: Sensitivity Analysis (Liver Volume Impact) ===\n\n")

    log("Goal: Manually sweep Liver Volume (0.75, 1.5, 3.0 L) to analyze impact on Brain Exposure.")
    
    # Baseline 1.5L
    volumes = [0.75, 1.5, 3.0]
    baseline_cmax = None
    
    for vol in volumes:
        sim_id = f"liv_vol_{vol}_{uuid.uuid4().hex[:4]}"
        log(f"\nRunning Scenario: Liver Volume={vol} L...")
        
        # Load
        call_tool("load_simulation", {
            "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
            "simulationId": sim_id
        }, critical=True)
        
        # Set Volume
        call_tool("set_parameter_value", {
            "simulationId": sim_id,
            "parameterPath": "Organism|Liver|Volume",
            "value": float(vol),
            "unit": None
        }, critical=True)
        
        # Run
        run_res = call_tool("run_simulation", {"simulationId": sim_id}, critical=True)
        job_id = run_res["jobId"]
        
        # Wait
        result_id = None
        for _ in range(30):
            res = call_tool("get_job_status", {"jobId": job_id})
            status = res["job"]["status"]
            if status == "succeeded":
                result_id = res["job"]["resultId"]
                break
            elif status in ["failed", "cancelled"]:
                log(f"  Failed: {res['job'].get('error')}")
                break
            time.sleep(1)
            
        if result_id:
            pk = call_tool("calculate_pk_parameters", {
                "simulationId": sim_id,
                "resultsId": result_id
            })
            
            # Extract Brain Cmax
            found = False
            for m in pk.get("metrics", []):
                if "Brain|Intracellular" in m["parameter"]:
                    cmax = m.get("cmax")
                    log(f"  -> Brain Cmax: {cmax:.2f} {m.get('unit')}")
                    if vol == 1.5:
                        baseline_cmax = cmax
                    elif baseline_cmax:
                        delta = (cmax - baseline_cmax) / baseline_cmax * 100
                        log(f"  -> Change from Baseline (1.5L): {delta:+.2f}%")
                    found = True
                    break
            if not found:
                log("  -> No Brain metric found")
        else:
            log("  -> Job failed or timeout")

if __name__ == "__main__":
    main()