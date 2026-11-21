import re

with open('PLAN.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

msg_batches = []
in_msg = False
for line in lines:
    if line.startswith('### MSG'):
        in_msg = True
        continue
    elif line.startswith('### '):
        in_msg = False
        continue
    if in_msg and line.strip().startswith('- ['):
        # - [ ] `MSG0000` 第 1 批 · 00001–01000 · 1,000 条
        m = re.search(r'- \[([ x])\] `([^`]+)`(?:\s+([^·]+))?\s+·\s+0*(\d+)–0*(\d+)\s+·\s+([0-9,]+)\s+条', line)
        if m:
            status, fname, part, start, end, cnt = m.groups()
            msg_batches.append({
                'raw_line': line.strip(),
                'status': status,
                'file': fname,
                'part': part.strip() if part else "",
                'start': int(start),
                'end': int(end),
                'count': int(cnt.replace(',', ''))
            })

print(f"Total MSG batches parsed: {len(msg_batches)}")
for b in msg_batches[:5]:
    print(b)
print("Last MSG batch:")
print(msg_batches[-1])
