#!/usr/bin/env python3
"""Best-effort public Rezultati.com football schedule fallback; never publishes bets."""
import argparse,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
ZONE=ZoneInfo("Europe/Sarajevo")
def scrape(day):
    fixtures=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(locale="hr-HR",timezone_id="Europe/Sarajevo")
        page.goto("https://www.rezultati.com/nogomet/",wait_until="domcontentloaded",timeout=35000)
        page.wait_for_timeout(4500)
        # Date navigation is deliberately not guessed: accept only the actual Sarajevo day.
        if day!=datetime.now(ZONE).date().isoformat():
            raise ValueError("Only today's live schedule is supported")
        for row in page.locator(".event__match").all():
            try:
                cls=row.get_attribute("class") or ""
                if "event__match--scheduled" not in cls and "event__match--live" in cls:continue
                home=row.locator(".event__participant--home").first.inner_text(timeout=500).strip()
                away=row.locator(".event__participant--away").first.inner_text(timeout=500).strip()
                clock=row.locator(".event__time").first.inner_text(timeout=500).strip()
                m=re.search(r"(?<!\\d)([01]?\\d|2[0-3]):([0-5]\\d)(?!\\d)",clock)
                if not m or not home or not away or home==away:continue
                start=datetime.fromisoformat(day+"T"+m.group(1).zfill(2)+":"+m.group(2)).replace(tzinfo=ZONE)
                if start<=datetime.now(ZONE)+timedelta(minutes=10):continue
                ident=row.get_attribute("id") or ""
                if not ident:continue
                fixtures.append({"id":"rezultati:"+ident,"provider":"rezultati.com-public-page","sport":"football","league":"unverified_competition","home":home,"away":away,"start_utc":start.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),"start_sarajevo":start.isoformat(),"status":"pre","coverage":"fallback_public_page","fixture_source_url":"https://www.rezultati.com/nogomet/"})
            except Exception:continue
        browser.close()
    return fixtures
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);ap.add_argument("--input",required=True);ap.add_argument("--output",required=True);ap.add_argument("--minimum",type=int,default=4)
    a=ap.parse_args();doc=json.loads(Path(a.input).read_text())
    existing=[x for x in doc.get("fixtures",[]) if x.get("sport")=="football" and x.get("status")=="pre"]
    if len(existing)>=a.minimum:
        print("ESPN sufficient:",len(existing));return
    try:extra=scrape(a.date)
    except Exception as e:
        doc.setdefault("errors",[]).append("Rezultati.com fallback unavailable: "+str(e)[:200])
        extra=[]
    seen={(x.get("home","").casefold(),x.get("away","").casefold(),x.get("start_sarajevo","")[:16]) for x in doc["fixtures"]}
    added=0
    for x in extra:
        key=(x["home"].casefold(),x["away"].casefold(),x["start_sarajevo"][:16])
        if key not in seen:
            doc["fixtures"].append(x);seen.add(key);added+=1
    doc["fixture_count"]=len(doc["fixtures"])
    doc.setdefault("sources",[]).append({"provider":"rezultati.com-public-page","status":"ok" if extra else "unavailable_or_empty","count":added})
    Path(a.output).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    print("Rezultati fallback added:",added)
if __name__=="__main__":main()
