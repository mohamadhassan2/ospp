import json
import yaml

def load_yaml(file_path):
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[!] Error loading {file_path}: {e}")
        return None

def validate_config():
    sources = load_yaml("sources.yaml")
    destinations = load_yaml("destinations.yaml")
    pipelines = load_yaml("pipelines.yaml")
    routes = load_yaml("routes.yaml")

    if not sources or not destinations or not pipelines or not routes:
        print("[!] Failed to load one or more configuration files.")
        return

    # Validate sources.yaml
    source_ids = set()
    line=0
    for source in sources.get("sources", []):
        line+=1
        if "source_id" not in source:
            print(f"[!] Missing 'source_id' in source: {line}:{source}")
        else:
            source_ids.add(source["source_id"])

    # Validate destinations.yaml
    destination_ids = set()
    line=0
    for dest in destinations.get("destinations", []):
        line+=1
        if "destination_id" not in dest:
            print(f"[!] Missing 'destination_id' in destination: {line}:{dest}")
        else:
            destination_ids.add(dest["destination_id"])

    # Validate pipelines.yaml
    pipeline_ids = set()
    line=0
    for pipeline in pipelines.get("pipelines", []):
        line+=1
        if "pipeline_id" not in pipeline:
            print(f"[!] Missing 'pipeline_id' in pipeline: {line}:{pipeline}")
        else:
            pipeline_ids.add(pipeline["pipeline_id"])

    # Validate routes.yaml
    line=0
    for route in routes.get("routes", []):
        #print (f"[---Routes: {json.dumps({routes}).encode(utf-8) }--\n")
        #print(f"",json.dumps(route, indent=4))
        line+=1
        if "source_id" not in route:
            print(f"[!] Missing 'source_id' in route: {line}{route}")
        elif route["source_id"] not in source_ids:
            print(f"[!] Invalid 'source_id' in route: {line}:{route['source_id']}")

        if "pipeline_id" not in route:
            print(f"[!] Missing 'pipeline_id' in route: {line}:{route}")
        elif route["pipeline_id"] not in pipeline_ids:
            print(f"[!] Invalid 'pipeline_id' in route: {line}:{route['pipeline_id']}")

        if "destination_ids" not in route:
            print(f"[!] Missing 'destination_ids' in route: {line}:{route}")
        else:
            for dest_id in route["destination_ids"]:
                if dest_id not in destination_ids:
                    print(f"[!] Invalid 'destination_id' in route: {line}:{dest_id}")

    print("[*] Validation complete with no errors.\n")

if __name__ == "__main__":
    validate_config()
