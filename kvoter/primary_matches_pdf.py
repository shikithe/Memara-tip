#!/usr/bin/env python3
"""Isolated test PDF: strictly primary name matches, no manual team aliases."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from kvoter import utc
from team_identity import normalize
from category_filter import excluded

def primary(f, o):
    if f.get("league") != o.get("league"): return False
    if excluded(f.get("home"),f.get("away"),f.get("league")): return False
    if excluded(o.get("home"),o.get("away"),o.get("league")): return False
    a,b=utc(f.get("start_utc")),utc(o.get("start_utc"))
    return bool(a and b and abs((a-b).total_seconds())<=5400
                and normalize(f.get("home"))==normalize(o.get("home"))
                and normalize(f.get("away"))==normalize(o.get("away")))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--history",required=True)
    ap.add_argument("--offers",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--json-output",required=True)
    a=ap.parse_args()
    history=json.loads(Path(a.history).read_text())["fixtures"]
    offers=json.loads(Path(a.offers).read_text())["offers"]
    matches=[]
    for f in history:
        hits=[o for o in offers if primary(f,o)]
        if hits: matches.append({"fixture":f,"offers":hits})
    data={"scope":"primary_only_no_manual_aliases","total_fixtures":len(history),"primary_matched":len(matches),"matches":matches}
    Path(a.json_output).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    pdfmetrics.registerFont(TTFont("DejaVu",font))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Kvoter",fontName="DejaVu",fontSize=9,leading=13))
    styles.add(ParagraphStyle(name="KvoterTitle",fontName="DejaVu",fontSize=16,leading=21,spaceAfter=12))
    doc=SimpleDocTemplate(a.output,pagesize=(595,842),rightMargin=34,leftMargin=34,topMargin=36,bottomMargin=36)
    story=[Paragraph("KVOTER — primarno upareni parovi",styles["KvoterTitle"]),
           Paragraph("Izolovani test. Samo automatsko uparivanje naziva bez ručnih aliasa. Kvote su iz API ponude; nisu prognoze.",styles["Kvoter"]),
           Spacer(1,10),
           Paragraph("Collector: %d utakmica | Primarno upareno: %d" % (len(history),len(matches)),styles["Kvoter"]),Spacer(1,12)]
    for i,m in enumerate(matches,1):
        f=m["fixture"]
        head="%d. %s — %s | %s | %s UTC" % (i,f.get("home"),f.get("away"),f.get("league"),f.get("start_utc"))
        rows=[["Kladionica","Tržište","Ishod","Kvota"]]
        for o in m["offers"]:
            for market,outcomes in sorted(o.get("markets",{}).items()):
                for outcome,price in outcomes.items():
                    if price is not None: rows.append([str(o.get("bookmaker") or ""),str(market),str(outcome),str(price)])
        if len(rows)==1: rows.append(["—","—","Nema cijena","—"])
        table=Table(rows,colWidths=[130,100,145,80],repeatRows=1,hAlign="LEFT")
        table.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),"DejaVu"),("FONTSIZE",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e7eef7")),("LINEBELOW",(0,0),(-1,0),0.5,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story.extend([Paragraph(head,styles["Kvoter"]),Spacer(1,5),table,Spacer(1,14)])
    if not matches: story.append(Paragraph("Nema primarno uparenih parova u ovom testu.",styles["Kvoter"]))
    doc.build(story)
    print("PRIMARY_PDF",a.output,"matched",len(matches),"offers",sum(len(m["offers"]) for m in matches))

if __name__=="__main__":main()
