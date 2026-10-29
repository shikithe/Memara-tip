#!/usr/bin/env python3
"""Supplement ESPN with today's public mobile Rezultati.com schedule.
Read-only fixture discovery; no odds, prediction, publication or bank changes.
"""
import argparse,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ZONE=ZoneInfo("Europe/Sarajevo")
URL="https://m.rezultati.com/"
TIME=re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)\s+(.+?)\s+-\s+(.+?)(?:\s+[-–]\s*)?$")
HEADER=re.compile(r"^[A-ZČĆŽŠĐ][A-ZČĆŽŠĐ\s&./'-]+:\s+.+")
def scrape(day):
    if day!=datetime.now(ZONE).date().isoformat():
        raise ValueError("Mobile homepage only supports the current Sarajevo day")
    req=Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; MemaraFixtureResearch/1.0)","Accept-Language":"hr-HR,hr;q=0.9"})
    with urlopen(req,timeout=25) as resp:
        raw=resp.read(3_000_001)
    if len(raw)>3_000_000:raise ValueError("Page too large")
    soup=BeautifulSoup(raw,"html.parser")
    for tag in soup(["script","style","noscript"]):tag.decompose()
    text=soup.get_text("\n",strip=True)
    if "Nogomet" not in text and "nogomet" not in text:
        raise ValueError("Page does not identify football schedule")
    lines=[re.sub(r"\s+"," ",s).strip() for s in text.splitlines() if s.strip()]
    # Mobile HTML frequently splits kickoff, home and away into separate nodes.
    # Reconstruct short adjacent lines without crossing section headings.
    candidates=[]
    for i,line in enumerate(lines):
        if re.match(r"^([01]?\d|2[0-3]):[0-5]\d(?:\s|$)",line):
            candidates.append(line)
            for n in (2,3,4):
                chunk=" ".join(lines[i:i+n])
                if any(HEADER.match(x) for x in lines[i+1:i+n]):break
                candidates.append(chunk)
    lines=list(dict.fromkeys(lines+candidates))
    print("REZULTATI_HTML_DIAGNOSTIC",json.dumps({"html_bytes":len(raw),"text_lines":len(lines),"time_candidates":len(candidates),"samples":candidates[:5]},ensure_ascii=False))
    league="unknown"
    fixtures=[]
    now=datetime.now(ZONE)
    for line in lines:
        if HEADER.match(line):
            league=line.split(" Tablica")[0]
            continue
        m=TIME.match(line)
        if not m:continue
        home,away=m.group(3).strip(),m.group(4).strip()
        if not home or not away or home==away:continue
        # Exclude completed scores and live status; reject ambiguous lines.
        if re.search(r"\b\d+\s*[-:]\s*\d+\b",away):continue
        if "Odgođeno" in line or "Postponed" in line:continue
        start=datetime.fromisoformat(day+"T"+m.group(1).zfill(2)+":"+m.group(2)).replace(tzinfo=ZONE)
        if start<=now+timedelta(minutes=10):continue
        fixtures.append({"id":"rezultati:"+str(len(fixtures)+1)+":"+day,"provider":"rezultati.com-mobile-public","sport":"football","league":league,"home":home,"away":away,"start_utc":start.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),"start_sarajevo":start.isoformat(),"status":"pre","fixture_source_url":URL})
    if not fixtures:raise ValueError("No parseable future football fixtures")
    return fixtures

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True);p.add_argument("--input",required=True);p.add_argument("--output",required=True);p.add_argument("--minimum",type=int,default=4)
    a=p.parse_args();doc=json.loads(Path(a.input).read_text(encoding="utf-8"))
    existing=[f for f in doc.get("fixtures",[]) if f.get("sport")=="football" and f.get("status")=="pre"]
    # Rezultati.com is primary: always attempt its daily schedule first.
    try:extra=scrape(a.date)
    except Exception as e:
        doc.setdefault("errors",[]).append("Rezultati mobile fallback failed: "+str(e)[:200]);extra=[]
    seen={(f.get("home","").casefold(),f.get("away","").casefold()) for f in doc["fixtures"]}
    added=0
    for f in extra:
        key=(f["home"].casefold(),f["away"].casefold())
        if key not in seen:
            doc["fixtures"].append(f);seen.add(key);added+=1
    doc["fixtures"].sort(key=lambda f:f["start_utc"])
    doc["fixture_count"]=len(doc["fixtures"])
    doc.setdefault("sources",[]).append({"provider":"rezultati.com-mobile-public","status":"ok" if added else "unavailable_or_empty","count":added,"url":URL})
    Path(a.output).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Rezultati mobile fallback: parsed",len(extra),"added",added,"total",len(doc["fixtures"]))
if __name__=="__main__":main()
