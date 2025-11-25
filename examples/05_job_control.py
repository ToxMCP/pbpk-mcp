import requests
import json
import time
import sys
import uuid

BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_05.txt"

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
        f.write("=== Use Case 5: Job Control (Status & Cancellation) ===\n\n")

    log("Goal: Submit a job and inspect its lifecycle status.")
    
    # 1. Load
    sim_id = f"job_ctrl_{uuid.uuid4().hex[:4]}"
    call_tool("load_simulation", {"filePath": "/app/var/Acetaminophen_Pregnancy.pkml", "simulationId": sim_id}, critical=True)
    
    # 2. Submit Run
    log("[1] Submitting Simulation...")
    run_res = call_tool("run_simulation", {"simulationId": sim_id}, critical=True)
    job_id = run_res["jobId"]
    log(f"    Job ID: {job_id}")
    
    # 3. Poll a few times
    for i in range(3):
        status_res = call_tool("get_job_status", {"jobId": job_id})
        status = status_res["job"]["status"]
        log(f"    Status (poll {i+1}): {status}")
        if status in ["succeeded", "failed"]:
            break
        time.sleep(0.5)
        
    # 4. Cancel (if not done)
    if status not in ["succeeded", "failed", "cancelled"]:
        log("\n[2] Requesting Cancellation...")
        cancel_res = call_tool("cancel_job", {"jobId": job_id})
        log(f"    Cancellation requested. Status: {cancel_res['status']}")
        
        time.sleep(1)
        final_res = call_tool("get_job_status", {"jobId": job_id})
        log(f"    Final Status: {final_res['job']['status']}")
    else:
        log("\n    Job finished too quickly to cancel (Expected for this fast model).")

if __name__ == "__main__":
    main()
