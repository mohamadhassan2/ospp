#------------------------------------------------------
# This module provides a pipeline engine for applying transformations to JSON data.
# It supports operations like regex replacements, converting fields to uppercase,
# and parsing JSON strings within fields.
#------------------------------------------------------

import re
import json

#------------------------------------------------------
def apply_pipeline(data: dict, steps: list) -> dict:
    for step in steps:
        t = step.get('type')
        if t == 'regex_replace':
            data = regex_replace(data, step)
        elif t == 'uppercase_field':
            data = uppercase_field(data, step)
        elif t == 'parse_json_string_field':
            data = parse_json_string_field(data, step)
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
            print(f"[!] Regex error: {e}")
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
            print(f"[!] Failed to parse JSON string in field '{field}': {e}")
    return data
# End of parse_json_string_field()
#------------------------------------------------------
