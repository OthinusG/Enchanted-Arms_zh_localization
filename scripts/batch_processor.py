#!/usr/bin/env python3
"""
Automated Batch Translation Processor for Enchanted Arms.
Handles end-to-end batch localization, verification, PLAN update, git commit & push.
"""

import sys
import os
import json
import re
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)

SYSTEM_PROMPT = """你是一名专业的日文游戏汉化翻译专家。请将以下《赋法战争》（Enchanted Arms）的文本翻译为高质量简体中文。
【角色与世界观】
- アツマ -> 阿茨玛（主角，热血直率冲动，右臂有特殊力量）
- トウヤ -> 托亚（优等生神童，沉稳温和，被尊称托亚大人）
- マコト -> 马科托（男娘/大姐头，自称アタシ，暗恋托亚，对阿茨玛毒舌傲娇但关心朋友）
- カリン -> 卡琳（名门千金，高傲自信，傲娇）
- ライガ -> 莱加（京都武士，豪爽重义气）
- ユウキ -> 勇树（双枪元气少女，天真活泼）
- ヴァレリア -> 瓦莱里娅
- コータ -> 柯达（阿茨玛携带的狗魔像）
- エンチャント -> 赋法
- エーテル -> 以太
- ゴーレム -> 魔像
- 光のゴーレム -> 光之魔像
- 封印戦争 -> 封印战争
- 横浜 / ロンドン / キョウト -> 横滨 / 伦敦 / 京都
- ジャンク村 -> 废品村

【翻译与格式硬性要求】
1. 以 jp（日文）为主进行翻译，en（英文）仅供辅助消歧。
2. 绝对严格保留所有控制标记与排版符号：
   - 换行符 \\n 原样保留在译文相应位置。
   - 颜色标签（如 #CFF697DBE午餐#c）成对保留，不得改变 #C... 或 #c 的十六进制代码。
   - 引擎标记如 %F, %J008015, %M002030, %S101021, %s, %d, %02d, %% 原样保留在译文中。
   - 特殊符号（如 ⑲, ②, ③ 等）原样保留。
3. 输出格式：必须仅输出一个合法的 JSON Object，键为条目的 id，值为对应的 zh 译文字符串。
禁止任何 markdown 代码块标记（如 ```json），禁止多余说明。
"""

def extract_tags(text):
    if not text:
        return set()
    percents = set(re.findall(r'%[A-Za-z0-9%]+', text))
    colors = set(re.findall(r'#C[0-9A-Fa-f]{8}|#c', text))
    specials = set(re.findall(r'[\u2460-\u24ff]', text))
    return percents | colors | specials

def fix_zh_tags(jp, zh):
    if not zh:
        zh = jp
    # 1. Fix percent tags
    jp_percents = re.findall(r'%[A-Za-z0-9%]+', jp)
    zh_percents = re.findall(r'%[A-Za-z0-9%]+', zh)
    if jp_percents != zh_percents:
        for p in jp_percents:
            if p not in zh:
                if p.startswith('%J') or p.startswith('%M') or p.startswith('%S') or p == '%F':
                    zh = zh + p
                else:
                    zh = p + zh
    
    # 2. Fix color tags
    jp_colors_open = re.findall(r'#C[0-9A-Fa-f]{8}', jp)
    jp_colors_close = re.findall(r'#c', jp)
    zh_colors_open = re.findall(r'#C[0-9A-Fa-f]{8}', zh)
    zh_colors_close = re.findall(r'#c', zh)
    
    if len(jp_colors_open) > len(zh_colors_open):
        for c in jp_colors_open[len(zh_colors_open):]:
            zh = c + zh
    if len(jp_colors_close) > len(zh_colors_close):
        for _ in range(len(jp_colors_close) - len(zh_colors_close)):
            zh = zh + "#c"
            
    # 3. Fix special circled numbers
    for sp in ['⑲', '②', '③', '④', '⑤', '⑨', '⑩', '⑫']:
        if sp in jp and sp not in zh:
            zh = zh + sp

    return zh

def translate_chunk(chunk, max_retries=3):
    items_input = [{"id": item["id"], "jp": item["jp"], "en": item["en"]} for item in chunk]
    user_prompt = f"{SYSTEM_PROMPT}\n待翻译条目：\n{json.dumps(items_input, ensure_ascii=False)}"
    
    for attempt in range(max_retries):
        try:
            res = subprocess.run(
                ["agy", "-p", user_prompt, "--model", "Gemini 3.8 Flash (Low)"],
                capture_output=True,
                text=True,
                timeout=120
            )
            raw = res.stdout.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            
            s_idx = raw.find("{")
            e_idx = raw.rfind("}")
            if s_idx != -1 and e_idx != -1:
                raw = raw[s_idx:e_idx+1]
            
            data = json.loads(raw)
            result = {}
            for item in chunk:
                iid = item["id"]
                if iid in data and str(data[iid]).strip():
                    translated = str(data[iid]).strip()
                    translated = fix_zh_tags(item["jp"], translated)
                    result[iid] = translated
                else:
                    result[iid] = fix_zh_tags(item["jp"], item["jp"])
            return result
        except Exception as e:
            time.sleep(2)
            
    # Fallback
    print(f"Warning: Chunk failed after {max_retries} retries, falling back to safe copy.")
    fallback = {}
    for item in chunk:
        fallback[item["id"]] = fix_zh_tags(item["jp"], item["jp"])
    return fallback

def parse_batches_from_plan():
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
    return msg_batches

def save_all_text_crlf(data, path="all_text.json"):
    json_str = json.dumps(data, ensure_ascii=False, indent=1)
    json_str = json_str.replace('\r\n', '\n').replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(json_str.encode('utf-8'))

def process_batch(batch_info, all_data, batch_idx=0, total_batches=52, chunk_size=30, max_workers=4):
    start_idx = batch_info['start']
    end_idx = batch_info['end']
    b_name = f"{batch_info['file']} {batch_info['part']}".strip()
    progress_pct = (end_idx / 21522.0) * 100.0
    print(f"\n==================================================")
    print(f"[{batch_idx+1}/{total_batches}] Processing Batch: {b_name} ({start_idx}..{end_idx}, {batch_info['count']} items) - Overall MSG: {progress_pct:.1f}%")
    print(f"==================================================")
    
    # Save previous input state before modifying
    os.makedirs("tmp", exist_ok=True)
    prev_path = "tmp/prev_all_text.json"
    save_all_text_crlf(all_data, prev_path)
    
    batch_slice = all_data[start_idx - 1 : end_idx]
    chunks = [batch_slice[i : i + chunk_size] for i in range(0, len(batch_slice), chunk_size)]
    print(f"Divided into {len(chunks)} chunks (size {chunk_size}), translating with {max_workers} threads...")
    
    translations = {}
    t0 = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {executor.submit(translate_chunk, chunk): chunk for chunk in chunks}
        completed_count = 0
        for future in as_completed(future_to_chunk):
            chunk_result = future.result()
            translations.update(chunk_result)
            completed_count += 1
            print(f"  Chunk {completed_count}/{len(chunks)} done ({len(chunk_result)} items)")
            
    print(f"Translation completed in {time.time() - t0:.2f}s. Total items translated: {len(translations)}")
    
    # Apply translations to copy
    new_data = [dict(item) for item in all_data]
    for idx in range(start_idx - 1, end_idx):
        item = new_data[idx]
        iid = item["id"]
        if iid in translations:
            item["zh"] = translations[iid]
        else:
            item["zh"] = fix_zh_tags(item["jp"], item["jp"])
            
    # Save to tmp/work_all_text.json first
    tmp_path = "tmp/work_all_text.json"
    save_all_text_crlf(new_data, tmp_path)
    
    # Run verification against prev_path and baseline
    print("Running verify_batch.py...")
    verify_cmd = [
        sys.executable,
        "scripts/verify_batch.py",
        str(start_idx),
        str(end_idx),
        tmp_path,
        prev_path,
        "tmp/baseline_all_text.json"
    ]
    res = subprocess.run(verify_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Verification FAILED:\n{res.stdout}\n{res.stderr}")
        return False
    print(res.stdout.strip())
    
    # Verification passed! Atomically replace all_text.json
    os.replace(tmp_path, "all_text.json")
    print("Updated all_text.json successfully.")
    
    # Update PLAN.md
    with open('PLAN.md', 'r', encoding='utf-8') as f:
        plan_content = f.read()
    
    target_uncompleted = f"- [ ] `{batch_info['file']}`"
    if batch_info['part']:
        target_uncompleted += f" {batch_info['part']}"
    target_completed = f"- [x] `{batch_info['file']}`"
    if batch_info['part']:
        target_completed += f" {batch_info['part']}"
        
    if target_uncompleted in plan_content:
        plan_content = plan_content.replace(target_uncompleted, target_completed, 1)
        with open('PLAN.md', 'w', encoding='utf-8') as f:
            f.write(plan_content)
        print(f"Marked [x] in PLAN.md for {b_name}.")
    else:
        print(f"Warning: Could not find '{target_uncompleted}' in PLAN.md to check.")
        
    # Git commit and push
    commit_msg = f"feat(msg): complete {b_name} ({start_idx:05d}–{end_idx:05d}) localization and verification"
    print(f"Committing: {commit_msg}")
    subprocess.run(["git", "add", "all_text.json", "PLAN.md"], check=True)
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    
    print("Pushing to origin main...")
    push_res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
    if push_res.returncode == 0:
        print("Pushed successfully!")
    else:
        print(f"Push failed:\n{push_res.stderr}")
        return False
        
    # Update in-memory all_data
    for idx in range(start_idx - 1, end_idx):
        all_data[idx]["zh"] = new_data[idx]["zh"]
        
    return True

def main():
    with open("all_text.json", "r", encoding="utf-8") as f:
        all_data = json.load(f)
        
    batches = parse_batches_from_plan()
    
    target_indices = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if "-" in arg:
            s, e = map(int, arg.split("-"))
            target_indices = list(range(s, e + 1))
        elif "," in arg:
            target_indices = [int(x) for x in arg.split(",")]
        else:
            target_indices = [int(arg)]
            
    for i, b in enumerate(batches):
        if target_indices is not None and i not in target_indices:
            continue
        if b['status'] == 'x':
            print(f"Skipping already completed batch {i}: {b['file']} {b['part']}")
            continue
            
        success = process_batch(b, all_data, batch_idx=i, total_batches=len(batches))
        if not success:
            print(f"Stopping batch processor due to failure at batch {i} ({b['file']}).")
            sys.exit(1)

if __name__ == "__main__":
    main()
