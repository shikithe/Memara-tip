# NBA SISTEM — istraživački checkpoint, 2026-11-21

Status: BLOCKED / NO PUBLICATION. Početak: 17:02 Europe/Berlin.

## Prethodna banka

nba-sistem.json potvrđuje ciklus 2026-11-20: settled, accounting.complete=true, bank_end=990.84 EUR, 10 tiketa. Novi dnevni ulog bi bio 9.91 EUR po tiketu (1%). Novi ciklus nije kreiran.

## Izvor ponude

BetSharp https://betsharp.com/nba/props?m=points pokazuje 68 igrača i 13 utakmica za narednih 48 sati, NE samo 24h. DK kolona ima linije i američke kvote, ali nismo uspjeli potvrditi kompletan izvorni 24h snapshot sa svim ESPN player_id, event_id i start_utc. N=68 nije validiran broj za naredna 24 sata. Nije dozvoljeno označiti ovaj djelimični uvid kao originalni zamrznuti snapshot.

ESPN scoreboard 2026-11-21 i 2026-11-22 je dohvatljiv, ali sadržaj ekstraktora nije validan JSON za potpuno i sigurno povezivanje svih igrača. Nije dozvoljeno izmišljati identifikatore.

## Scout i objave

0 kompletnih per-player Full Scout audita potvrđeno (L5, H2H, matchup, injury, bookmaker odds, ESPN IDs). 0 rang-tabela, 0 novih tiketa. Sljedeći korak: originalni kompletan DK BetSharp 24h snapshot sa numeričkim ESPN ID-evima, provjera kroz nba_system_pipeline.py validate-snapshot, zatim 10 grupa redom, puna tabela svake grupe, objava tek poslije validacije. Ne mijenjati A/B/C.

Izvori: https://betsharp.com/nba/props?m=points ; https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261121 ; https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261122
