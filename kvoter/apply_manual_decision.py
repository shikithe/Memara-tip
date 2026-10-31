#!/usr/bin/env python3
"""Apply authenticated GitHub issue decisions, validating against published candidate evidence."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from workflow import safe_identity
def main():
    event=json.loads(Path(sys.argv[1]).read_text())
    issue=event['issue']
    if issue['user']['login'].lower()!='shikithe': raise SystemExit('Only repository owner may approve Kvoter matches')
    title=issue.get('title','')
    if title not in ('KVOTER MATCH','KVOTER REJECT','KVOTER BATCH'):raise SystemExit('Unknown decision')
    payload=json.loads(issue['body'])
    items=payload.get('decisions',[]) if title=='KVOTER BATCH' else [dict(payload,decision='matched' if title=='KVOTER MATCH' else 'rejected')]
    if not isinstance(items,list) or not 1<=len(items)<=100:raise SystemExit('Invalid batch')
    if len({(x.get('fixture_id'),x.get('event_id')) for x in items})!=len(items):raise SystemExit('Duplicates')
    queue=json.loads(Path(sys.argv[2]).read_text())
    path=Path('kvoter/manual/decisions.json')
    doc=json.loads(path.read_text()) if path.exists() else {'decisions':[]}
    dbpath=Path('kvoter/team-database.json')
    db=json.loads(dbpath.read_text())
    validated=[]
    for item in items:
        if item.get('decision') not in ('matched','rejected'):raise SystemExit('Invalid decision')
        fixture=next((f for f in queue['fixtures'] if f['fixture_id']==item.get('fixture_id')),None)
        if not fixture:raise SystemExit('Fixture missing')
        candidate=next((o for o in fixture['candidates'] if o['event_id']==item.get('event_id')),None)
        if not candidate or candidate['league']!=fixture['league']:raise SystemExit('Invalid Odds event')
        decision={'fixture_id':fixture['fixture_id'],'event_id':candidate['event_id'],'collector_home':fixture['home'],'collector_away':fixture['away'],'odds_home':candidate['home'],'odds_away':candidate['away'],'league':fixture['league'],'decision':item['decision'],'issue_number':issue['number']}
        if item['decision']=='matched':
            for a,b in [(fixture['home'],candidate['home']),(fixture['away'],candidate['away'])]:
                if a!=b and not safe_identity(db,fixture['league'],[a,b],sources=['github-issue-'+str(issue['number'])]):
                    raise SystemExit('Unsafe identity')
        validated.append(decision)
    keys={(x['fixture_id'],x['event_id']) for x in validated}
    doc['decisions']=[x for x in doc['decisions'] if (x['fixture_id'],x['event_id']) not in keys]
    doc['decisions'].extend(validated)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\\n')
    dbpath.write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\\n')
    print('KVOTER_DECISIONS_SAVED',len(validated))

if __name__=='__main__':main()
