import json
import sys

def main():
    json_objects = []
    
    for line in sys.stdin:
        line = line.strip()
        if line:  # Skip empty lines
            try:
                json_obj = json.loads(line)
                json_objects.append(json_obj)
            except json.JSONDecodeError as e:
                print(f"Error parsing line: {line}", file=sys.stderr)
                print(f"JSON Error: {e}", file=sys.stderr)
                sys.exit(1)
    
    # Output as pretty-printed JSON array
    print(json.dumps(json_objects, indent=2))

if __name__ == "__main__":
    main()
