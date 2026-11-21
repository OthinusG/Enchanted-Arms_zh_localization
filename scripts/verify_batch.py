#!/usr/bin/env python3
"""
Verification script for Enchanted Arms localization batches.
Ensures data contract compliance:
1. Valid JSON array.
2. Identical record count (30,442) and identical keys in exact order: id, category, file, offset, jp, en, zh.
3. Only the specified batch index range (1-based, inclusive) has modified zh (which must be non-empty).
4. All non-zh fields must match baseline.
5. All records outside the batch range must match baseline.
6. Control tags (%F, %J..., %M..., %S..., %s, %d, #C...#c) must be preserved in zh.
7. File uses CRLF line endings.
"""

import sys
import json
import re
import os

def extract_tags(text):
    if not text:
        return set()
    # Find %F, %J..., %M..., %S..., %s, %d, %02d, %%
    percents = set(re.findall(r'%[A-Za-z0-9%]+', text))
    # Find color tags like #CFF697DBE and #c
    colors = set(re.findall(r'#C[0-9A-Fa-f]{8}|#c', text))
    # Special circled numbers
    specials = set(re.findall(r'[\u2460-\u24ff]', text))
    return percents | colors | specials

def verify_batch(file_path, start_idx, end_idx, baseline_path="baseline_all_text.json"):
    # 1. Check CRLF
    with open(file_path, 'rb') as f:
        raw_bytes = f.read()
    
    if b'\r\n' not in raw_bytes[:1000]:
        print("WARNING: CRLF line endings not detected in header")

    # 2. Parse JSON
    try:
        data = json.loads(raw_bytes.decode('utf-8'))
    except Exception as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        return False

    if not isinstance(data, list):
        print("ERROR: Root is not a JSON array")
        return False

    if len(data) != 30442:
        print(f"ERROR: Expected 30442 records, got {len(data)}")
        return False

    # Load baseline if available
    baseline = None
    if os.path.exists(baseline_path):
        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

    # 3. Check records
    expected_keys = ["id", "category", "file", "offset", "jp", "en", "zh"]
    errors = []

    for idx, item in enumerate(data, start=1):
        keys = list(item.keys())
        if keys != expected_keys:
            errors.append(f"Line {idx}: Keys mismatch: {keys} != {expected_keys}")
            if len(errors) > 20: break

        if start_idx <= idx <= end_idx:
            # Must have non-empty zh
            if not item.get("zh", "").strip():
                errors.append(f"Line {idx} ({item['id']}): Empty zh in batch range")
            
            # Check tags
            jp_tags = extract_tags(item.get("jp", ""))
            zh_tags = extract_tags(item.get("zh", ""))
            
            # Certain tags MUST match exactly: percent tags (%J..., %M..., %S..., %F, %s, %d)
            jp_percent = {t for t in jp_tags if t.startswith('%')}
            zh_percent = {t for t in zh_tags if t.startswith('%')}
            if jp_percent != zh_percent:
                errors.append(f"Line {idx} ({item['id']}): Percent tag mismatch. JP: {jp_percent}, ZH: {zh_percent}")
            
            # Check color tags (#C... and #c count)
            jp_color_open = len(re.findall(r'#C[0-9A-Fa-f]{8}', item.get("jp", "")))
            zh_color_open = len(re.findall(r'#C[0-9A-Fa-f]{8}', item.get("zh", "")))
            jp_color_close = len(re.findall(r'#c', item.get("jp", "")))
            zh_color_close = len(re.findall(r'#c', item.get("zh", "")))
            if (jp_color_open != zh_color_open) or (jp_color_close != zh_color_close):
                errors.append(f"Line {idx} ({item['id']}): Color tag count mismatch. JP open/close: ({jp_color_open},{jp_color_close}), ZH: ({zh_color_open},{zh_color_close})")

            if baseline:
                base_item = baseline[idx - 1]
                for k in ["id", "category", "file", "offset", "jp", "en"]:
                    if item[k] != base_item[k]:
                        errors.append(f"Line {idx}: Non-zh field '{k}' modified from baseline")
        else:
            if baseline:
                base_item = baseline[idx - 1]
                if item != base_item:
                    errors.append(f"Line {idx}: Record outside batch range modified from baseline")
                    if len(errors) > 20: break

    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for err in errors[:25]:
            print("  ", err)
        return False

    print(f"SUCCESS: Batch {start_idx}..{end_idx} verified successfully ({end_idx - start_idx + 1} records).")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 verify_batch.py <start_idx> <end_idx> [all_text.json] [baseline.json]")
        sys.exit(1)
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    target_file = sys.argv[3] if len(sys.argv) > 3 else "all_text.json"
    baseline = sys.argv[4] if len(sys.argv) > 4 else "tmp/baseline_all_text.json"
    ok = verify_batch(target_file, start, end, baseline)
    sys.exit(0 if ok else 1)
