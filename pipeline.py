#------------------------------------------------------
# This module provides a pipeline engine for applying transformations to JSON data.
# It supports operations like regex replacements, converting fields to uppercase,
# and parsing JSON strings within fields.
#------------------------------------------------------

import re
import json

from colorama import Fore
from utils import debug_print  # Import debug_print from utils.py

#------------------------------------------------------
def apply_pipeline(data: dict, steps: list) -> dict:
    debug_print(f"[+] Applying pipeline with {len(steps)} steps.", DLevel=2)
    for step in steps:
        t = step.get('type')
        try:
            if t == 'regex_replace':
                pattern = step['pattern']
                replacement = step['replacement']
                field = step['field']
                debug_print(f"[>] Applying regex_replace on field '{field}' with pattern '{pattern}'", DLevel=3)
                data[field] = re.sub(pattern, replacement, data[field])
            elif t == 'uppercase_field':
                data = uppercase_field(data, step)
            elif t == 'parse_json_string_field':
                data = parse_json_string_field(data, step)
        except Exception as e:
            debug_print(f"[!] Error applying pipeline step: {step} - Error: {e}", DLevel=0)
    return data
# End of apply_pipeline()
#------------------------------------------------------

#------------------------------------------------------
def regex_replace(data, step):
    field = step.get("field")
    pattern = step.get("pattern")
    replacement = step.get("replacement", "")
    value = data.get(field, "")
    if isinstance(value, str):
        try:
            data[field] = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        except re.error as e:
            print(f"{Fore.RED}[!] Regex error: {e}", flush=True)
    return data
# End of regex_replace()
#------------------------------------------------------

#------------------------------------------------------
def uppercase_field(data, step):
    field = step.get("field")
    if field in data and isinstance(data[field], str):
        data[field] = data[field].upper()
    return data
# End of uppercase_field()
#------------------------------------------------------

#------------------------------------------------------
def parse_json_string_field(data, step):
    field = step.get("field")
    if field in data and isinstance(data[field], str):
        try:
            data[field] = json.loads(data[field])
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to parse JSON string in field '{field}': {e}")
    return data
# End of parse_json_string_field()
#------------------------------------------------------
