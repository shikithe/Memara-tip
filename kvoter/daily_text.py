#!/usr/bin/env python3
"""Daily read-only football list, from this exact isolated collector+odds run."""
import argparse,json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--history',required=True)
p.add_argument('--matched',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
history=json.loads(Path(a.history).read_text())
matched=json.loads(Path(a.matched).read_text())
by_id={x['fixture_id']:x for x in matched['fixtures']}
generated=history.get('generated_at_utc','')
lines=['KVOTER — DNEVNA LISTA UTAKMICA',
       'Preuzeto: '+generated+' (UTC)',
       'Ukupno u Collector ponudi: '+str(len(history['fixtures'])),
       'Automatski upareno: '+str(len(by_id)),
       'Neupareno u ovom ciklusu: '+str(len(history['fixtures'])-len(by_id)),
       'Vrijeme utakmica: Europe/Sarajevo',
       'Napomena: ručno potvrđeni parovi postaju automatski upareni tek u narednoj obradi.',
       'Kvote su informativne, iz trenutka preuzimanja; nisu uživo.','']
for i,f in enumerate(history['fixtures'],1):
    when=datetime.fromisoformat(f['start_utc'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Sarajevo'))
    m=by_id.get(f['fixture_id'])
    lines.append(f"{i:02d}. {f['home']} – {f['away']} | {when:%d.%m. %H:%M} | {f.get('league','')} | "+('UPARENO' if m else 'ZA PROVJERU'))
    if m:
        offers=m.get('odds_offers',[])
        pref=next((o for key in ('pinnacle','bet365') for o in offers if o.get('bookmaker')==key),None)
        if not pref and offers: pref=offers[0]
        if pref:
            markets=pref.get('markets',{})
            one=markets.get('1X2',{})
            over=markets.get('3+',{})
            lines.append('    '+str(pref.get('bookmaker',''))+' | 1: '+str(one.get('home','-'))+' X: '+str(one.get('draw','-'))+' 2: '+str(one.get('away','-'))+' | 3+: '+str(over.get('over','-')))
    lines.append('')
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
Path(a.output).write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('DAILY_TEXT_CREATED',len(history['fixtures']))
