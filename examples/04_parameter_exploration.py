import requests
import json
import sys
import uuid

BASE_URL = "http://localhost:8000/mcp/call_tool"
HEADERS = {"Content-Type": "application/json"}
OUTPUT_FILE = "examples/output_04.txt"

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
        f.write("=== Use Case 4: Parameter Exploration & Inspection ===\n\n")

    log("Goal: Demonstrate model introspection tools (listing and reading parameters).")
    
    # 1. Load Model
    log("\n[1] Loading Model...")
    sim_id = f"expl_{uuid.uuid4().hex[:4]}"
    call_tool("load_simulation", {
        "filePath": "/app/var/Acetaminophen_Pregnancy.pkml",
        "simulationId": sim_id
    }, critical=True)
    
    # 2. List Parameters (Search for 'Cmax' or 'Liver')
    log("\n[2] Searching for 'Liver Volume' parameters...")
    # Note: R adapter regex matching can be tricky, "Liver" substring works
    list_res = call_tool("list_parameters", {
        "simulationId": sim_id,
        "searchPattern": "Liver" 
    })
    
    params = list_res.get("parameters", [])
    log(f"    Found {len(params)} parameters matching 'Liver'.")
    
    target_param = None
    for p in params:
        # The list return is a list of strings (paths) or dicts?
        # The adapter implementation returns a list of objects, but the bridge R script returns strings?
        # Let's check what we receive.
        path = p
        if isinstance(p, dict):
            path = p.get("path")
            
        if "Organism|Liver|Volume" == path:
            target_param = path
            break
            
    if target_param:
        log(f"    Target Identified: {target_param}")
        
        # 3. Get Parameter Value
        log(f"\n[3] Inspecting Value for: {target_param}")
        get_res = call_tool("get_parameter_value", {
            "simulationId": sim_id,
            "parameterPath": target_param
        })
        
        val = get_res["parameter"]
        log(f"    Current Value: {val.get('value')} {val.get('unit')}")
        
        # 4. Verify Update
        log("\n[4] Verifying Update Capability...")
        call_tool("set_parameter_value", {
            "simulationId": sim_id,
            "parameterPath": target_param,
            "value": 2.0,
            "unit": val.get('unit')
        }, critical=True)
        
        get_res_2 = call_tool("get_parameter_value", {
            "simulationId": sim_id,
            "parameterPath": target_param
        })
        new_val = get_res_2["parameter"]
        log(f"    New Value:     {new_val.get('value')} {new_val.get('unit')}")
        
    else:
        log("    Could not find 'Organism|Liver|Volume' in search results.")
        # Dump first 5 for debugging
        for p in params[:5]:
            log(f"    - {p}")

if __name__ == "__main__":
    main()
