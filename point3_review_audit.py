#!/usr/bin/env python3
"""Audit point-3 review fixtures without guessing provider mappings."""
import json
from collections import Counter, defaultdict
from pathlib import Path
p=Path("collector-output/statistics-filter.json")
d=json.loads(p.read_text(encoding="utf-8"))
rows=[x for x in d["fixtures"] if x["point3"]=="review"]
reasons=Counter(x["reason"] for x in rows)
leagues=defaultdict(Counter)
for x in rows: leagues[x.get("league") or "Unknown"][x["reason"]]+=1
out={"review_total":len(rows),"reasons":dict(reasons),
     "leagues":[{"league":league,"total":sum(counts.values()),"reasons":dict(counts)}
               for league,counts in sorted(leagues.items(),key=lambda z:-sum(z[1].values()))],
     "note":"No candidates promoted without verified provider identity and minimum history. Review is not rejection.",
     "review_fixtures":rows}
dest=Path("collector-output/point3-review-audit.json")
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("POINT3 REVIEW TOTAL:",len(rows))
print("REASONS:",json.dumps(dict(reasons)))
print("TOP LEAGUES:")
for entry in out["leagues"][:30]:
 print(f"  {entry['total']:3d} | {entry['league']} | {entry['reasons']}")
print("Audit artifact:",dest)
