#!/usr/bin/env python3
"""扫描 Wiki 目录，生成 stats.json 供仪表盘使用"""
import os, json, re, time
from datetime import datetime

WIKI = "/home/admin/wiki-info-sec"
PAGE_DIRS = ["entities", "concepts", "comparisons", "queries"]

# 加载板块配置
with open(os.path.join(WIKI, "domains.json")) as f:
    DOMAINS = json.load(f)["domains"]

def parse_frontmatter(md_text):
    match = re.match(r'^---\n(.*?)\n---', md_text, re.DOTALL)
    if not match:
        return {}
    data = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith('[') and val.endswith(']'):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
            data[key] = val
    return data

# 构建 tag → domain 映射
tag_to_domain = {}
for dm in DOMAINS:
    for tag in dm["tags"]:
        tag_to_domain[tag] = dm["id"]

def classify_domain(tags, explicit_domain):
    """根据 frontmatter domain 字段或标签判断所属板块"""
    if explicit_domain:
        for dm in DOMAINS:
            if dm["id"] == explicit_domain:
                return dm["id"]
    for tag in tags:
        if tag in tag_to_domain:
            return tag_to_domain[tag]
    return "other"

def scan_wiki():
    pages = []
    tags_count = {}
    type_count = {"entity": 0, "concept": 0, "comparison": 0, "query": 0}
    confidence_count = {"high": 0, "medium": 0, "low": 0}
    domain_count = {dm["id"]: 0 for dm in DOMAINS}
    domain_count["other"] = 0
    contested = 0
    total = 0
    
    for d in PAGE_DIRS:
        dirpath = os.path.join(WIKI, d)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(dirpath, fname)
            mtime = os.path.getmtime(fpath)
            
            with open(fpath, 'r') as f:
                fm = parse_frontmatter(f.read())
            
            domain = classify_domain(fm.get("tags", []), fm.get("domain", ""))
            
            page = {
                "title": fm.get("title", fname.replace('.md', '').replace('-', ' ').title()),
                "type": fm.get("type", d.rstrip('s')),
                "path": f"{d}/{fname}",
                "tags": fm.get("tags", []),
                "domain": domain,
                "created": fm.get("created", ""),
                "updated": fm.get("updated", ""),
                "confidence": fm.get("confidence", ""),
                "contested": fm.get("contested", False),
                "mtime": int(mtime),
            }
            pages.append(page)
            total += 1
            
            t = page["type"]
            if t in type_count:
                type_count[t] += 1
            
            for tag in page["tags"]:
                tags_count[tag] = tags_count.get(tag, 0) + 1
            
            if page["confidence"] in confidence_count:
                confidence_count[page["confidence"]] += 1
            if page["contested"]:
                contested += 1
            
            if domain in domain_count:
                domain_count[domain] += 1
    
    pages_by_updated = sorted(pages, key=lambda p: p["mtime"], reverse=True)
    top_tags = sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:25]
    
    now = time.time()
    trend = {"30d": 0, "14d": 0, "7d": 0}
    for p in pages:
        if now - p["mtime"] < 7*86400: trend["7d"] += 1
        if now - p["mtime"] < 14*86400: trend["14d"] += 1
        if now - p["mtime"] < 30*86400: trend["30d"] += 1
    
    # 板块统计（带 emoji 和名称）
    domain_stats = []
    for dm in DOMAINS:
        domain_stats.append({
            "id": dm["id"], "name": dm["name"], "emoji": dm["emoji"],
            "count": domain_count.get(dm["id"], 0)
        })
    if domain_count.get("other", 0) > 0:
        domain_stats.append({"id": "other", "name": "其他", "emoji": "📦", "count": domain_count["other"]})
    
    stats = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_pages": total,
        "type_count": type_count,
        "top_tags": [{"name": t, "count": c} for t, c in top_tags],
        "domains": domain_stats,
        "confidence_count": confidence_count,
        "contested": contested,
        "recent": [{
            "title": p["title"], "type": p["type"], "path": p["path"],
            "domain": p["domain"], "tags": p["tags"][:3], "updated": p["updated"],
        } for p in pages_by_updated[:10]],
        "trend": trend,
    }
    
    return stats

if __name__ == "__main__":
    stats = scan_wiki()
    outpath = os.path.join(WIKI, "stats.json")
    with open(outpath, 'w') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # Also output page list for domain filtering
    # Load sub_domain mapping
    sub_map = {}
    sub_conf = os.path.join(WIKI, "sub_domains.json")
    if os.path.exists(sub_conf):
        with open(sub_conf) as f:
            sub_map = json.load(f).get("mapping", {})
    
    pages_list = []
    for d in PAGE_DIRS:
        dirpath = os.path.join(WIKI, d)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, 'r') as f:
                fm = parse_frontmatter(f.read())
            domain = classify_domain(fm.get("tags", []), fm.get("domain", ""))
            rel_path = f"{d}/{fname}"
            pages_list.append({
                "title": fm.get("title", fname.replace('.md', '').replace('-', ' ').title()),
                "type": fm.get("type", d.rstrip('s')),
                "path": rel_path,
                "domain": domain,
                "sub_domain": sub_map.get(rel_path, ""),
                "tags": fm.get("tags", [])[:5],
                "updated": fm.get("updated", ""),
            })
    
    list_path = os.path.join(WIKI, "page_list.json")
    with open(list_path, 'w') as f:
        json.dump(pages_list, f, ensure_ascii=False, indent=2)
    
    print(f"✅ stats.json: {stats['total_pages']} 页, {len(DOMAINS)} 板块")
    print(f"✅ page_list.json: {len(pages_list)} 条")
