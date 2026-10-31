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
    if title not in ('KVOTER MATCH','KVOTER REJECT'): raise SystemExit('Unrecognized decision')
    payload=json.loads(issue['body'])
    queue=json.loads(Path(sys.argv[2]).read_text())
    fixture=next((f for f in queue['fixtures'] if f['fixture_id']==payload.get('fixture_id')),None)
    if not fixture:raise SystemExit('Fixture not in active candidate queue')
    candidate=next((o for o in fixture['candidates'] if o['event_id']==payload.get('event_id')),None)
    if not candidate:raise SystemExit('Odds event not in candidate queue')
    if candidate['league']!=fixture['league']:raise SystemExit('League mismatch')
    decision={'fixture_id':fixture['fixture_id'],'event_id':candidate['event_id'],'collector_home':fixture['home'],'collector_away':fixture['away'],'odds_home':candidate['home'],'odds_away':candidate['away'],'league':fixture['league'],'decision':'matched' if title=='KVOTER MATCH' else 'rejected','issue_number':issue['number']}
    path=Path('kvoter/manual/decisions.json')
    doc=json.loads(path.read_text()) if path.exists() else {'decisions':[]}
    doc['decisions']=[x for x in doc['decisions'] if not (x['fixture_id']==decision['fixture_id'] and x['event_id']==decision['event_id'])]
    doc['decisions'].append(decision)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    if title=='KVOTER MATCH':
        dbpath=Path('kvoter/team-database.json')
        db=json.loads(dbpath.read_text())
        for a,b in [(fixture['home'],candidate['home']),(fixture['away'],candidate['away'])]:
            if a!=b and not safe_identity(db,fixture['league'],[a,b],sources=['github-issue-'+str(issue['number'])]):
                raise SystemExit('Ambiguous or unsafe identity: '+a+' / '+b)
        dbpath.write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\n')
    print('KVOTER_DECISION',decision['decision'],decision['fixture_id'],decision['event_id'])
if __name__=='__main__':main()
