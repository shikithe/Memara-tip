#!/usr/bin/env python3
"""Daily site publication: never invent odds, research, or bets."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
def read(path):
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

def main():
    now = datetime.now(ZoneInfo("Europe/Sarajevo"))
    today = now.date().isoformat()
    old = read("data.json")
    if old.get("date") == today and any(t.get("status","").startswith("objavljen") for t in old.get("tickets",[])):
        print("Existing published tickets are immutable; skipping.")
        return
    # Fail closed: this script has no verified bookmaker quote ingestion or analyst selection.\n    # Never overwrite real tickets, archive, or bankroll with a status-only placeholder.\n    print("PUBLICATION_BLOCKED: no verified A/B/C selection pipeline; data.json unchanged.")\n    return\n    bank = float(old.get("bank_after_stakes",old.get("bank_after",old.get("bank_before",0))))
    queue = read("collector-output/unified-analysis-queue.json")
    independent = read("collector-output/independent-analysis.json")
    fresh_queue = queue.get("date") == today
    fresh_independent = independent.get("date") == today
    count = len(queue.get("analyst_queue",[])) if fresh_queue else 0
    notes = [
        f"Statistički pokrivenih kandidata: {count}" if fresh_queue else "Nema današnjeg potvrđenog statističkog izvještaja.",
        "Nezavisna analiza kandidata postoji, ali nema potvrđene tržišne kvote." if fresh_independent else "Nezavisna analiza nije potvrđena za današnji datum.",
        "Javni prikazi Mozzart/Bet365 nisu automatski potvrđeni; ne objavljuj izmišljene kvote.",
    ]
    tickets = []
    for code,label in [("A","GLAVNI TIKET"),("B","GOLOVI 3+"),("C","KEŠ KOLICA")]:
        tickets.append({"id":code,"label":label+" — ČEKA PROVJERU","odds":None,"stake":0,"status":"preskočen","payout":0,"matches":[],"analysis":{"summary":"Nema pouzdano provjerenih tipova za automatsku objavu.","reasons":notes,"limits":"Nema automatskog klađenja, ni promjene banke bez provjerenih kvota."}})
    report = {
        "date":today,"published":now.strftime("%d.%m.%Y. u %H:%M · automatski dnevni izvještaj"),
        "publication_type":"status_only_no_verified_bets",
        "bank_before":bank,"daily_stake":0,"bank_after":bank,"bank_after_stakes":bank,
        "provisional":False,"odds_verified":False,
        "odds_verification_note":"Nema automatskog, pravovremenog i provjerenog Mozzart/Bet365 feeda.",
        "tickets":tickets,"analysis_status":" | ".join(notes),
        "selection_method":"Automatski sigurnosni filter: bez potvrđenih kvota i analize nema tipova.",
        "settled":True,"total_payout":0,"net_change":0,
    }
    (ROOT/"data.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Published {today}: {count} candidates, 0 unverified bets, bank {bank:.2f}")
if __name__=="__main__":
    main()
