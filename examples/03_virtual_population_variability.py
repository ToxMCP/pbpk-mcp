import requests
import json
import time
import sys
import uuid

# Configuration
BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_03.txt"

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
        try:
            log(str(response.json()))
        except:
            pass
        sys.exit(1)
    return response.json()["structuredContent"]

def run_individual(age, bmi):
    sim_id = f"ind_{age}_{bmi}_{uuid.uuid4().hex[:4]}"
    log(f"\nRunning Individual: Age={age}y, BMI={bmi}...")
    
    # Load (New instance for parallel safety if needed, though here serial)
    call_tool("load_simulation", {
        "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": sim_id
    }, critical=True)
    
    # Set Params
    call_tool("set_parameter_value", {
        "simulationId": sim_id,
        "parameterPath": "Organism|Age",
        "value": float(age),
        "unit": None
    }, critical=True)
    
    call_tool("set_parameter_value", {
        "simulationId": sim_id,
        "parameterPath": "Organism|BMI",
        "value": float(bmi),
        "unit": None
    }, critical=True)
    
    # Run
    run_res = call_tool("run_simulation", {"simulationId": sim_id}, critical=True)
    job_id = run_res["jobId"]
    
    # Wait
    result_id = None
    for _ in range(30):
        status = call_tool("get_job_status", {"jobId": job_id})["job"]["status"]
        if status == "succeeded":
            result_id = status_res = call_tool("get_job_status", {"jobId": job_id})["job"]["resultId"]
            break
        elif status in ["failed", "cancelled"]:
            log(f"Failed: {status}")
            return None
        time.sleep(1)
        
    if not result_id:
        log("Timeout")
        return None
        
    # Get Metrics
    pk = call_tool("calculate_pk_parameters", {
        "simulationId": sim_id,
        "resultsId": result_id
    })
    
    # Return Cmax for Brain
    for m in pk.get("metrics", []):
        if "Brain|Intracellular" in m["parameter"]:
            return m.get("cmax")
    return 0.0

def main():
    # Clear output file
    with open(OUTPUT_FILE, "w") as f:
        f.write("=== Use Case 3: Virtual Population (Manual Loop) ===\n\n")

    log("Goal: Simulate 3 virtual individuals with different physiology (Age, BMI) and compare Brain Cmax.")
    
    cohort = [
        {"age": 20, "bmi": 20},
        {"age": 40, "bmi": 25},
        {"age": 60, "bmi": 30}
    ]
    
    results = []
    
    for subject in cohort:
        cmax = run_individual(subject["age"], subject["bmi"])
        if cmax is not None:
            log(f"  -> Brain Cmax: {cmax:.2f}")
            results.append(cmax)
        else:
            log("  -> Failed")
            
    if results:
        avg = sum(results) / len(results)
        log(f"\nPopulation Average Brain Cmax: {avg:.2f}")

if __name__ == "__main__":
    main()
