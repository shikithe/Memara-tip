# MemaraSix — trajno pravilo pracenja rezultata i vremena

Datum potvrde: 2026-11-23.

Ovaj dokument predstavlja stalni funkcionalni zahtjev projekta. Ne mijenjati ga
pri izmjenama izgleda ili drugih automatizacija bez izricite saglasnosti korisnika.

## Obavezno pracenje

1. Svaki objavljeni fudbalski par na tiketima A/B prati se po izvornom
   `fixture_id = espn:football:<league>:<event_id>`, ne po slobodnom poredjenju
   imena klubova. Prikazati zakazani pocetak po Europe/Sarajevo / Europe/Berlin,
   rezultat, minut dok traje mec, status pauze i konacni rezultat.
2. Tiket C: ESPN `espn_event_id` + `player_id`; prikazati poene igraca,
   granicu poena, cetvrtinu i preostalo vrijeme kada je dostupno.
3. Nezavisni NBA SISTEM 10: za svakog igraca prikazati poene, cetvrtinu,
   game clock i zavrsni ishod, bez diranja nezavisne banke A/B/C.
4. Fudbalski tipovi 2+, 3+ i GG se oznacavaju pogodenim kada je njihov
   uspjeh nepovratan, cak i ako je mec jos u toku. Tipovi koji mogu
   promijeniti ishod zakljucuju se tek po zavrsetku. NBA OVER postaje
   pogodjen pri prelasku granice, NBA UNDER se potvrduje tek po zavrsetku;
   nepovratni UNDER promasaj oznacava se odmah.
5. Izostanak igraca (DNP/VOID) sa koeficijentom 1.00 priznaje se samo
   kada je ESPN boxscore zavrsen i nedvosmisleno potvrden.
6. Nakon objave novog tiketa odabrani publisher mora traziti trenutno
   pokretanje relevantnog live workflowa. Raspored je pomocni (GitHub
   cron moze zakasniti); browser moze samo prikazivati direktno
   provjerene ESPN podatke uz oznaku izvora.
7. Sajt obnavlja podatke pri otvaranju, povratku u karticu i periodicno
   dok je kartica aktivna. Nikad ne prikazivati zastarjeli rezultat kao
   svjez live; pokazati vrijeme posljednjeg izvjestaja.
8. UI browser osvjezavanje nikad ne mijenja banku, statuse objavljenih
   tiketa ili arhivu. Samo GitHubov provjereni idempotentni settlement
   smije mijenjati status i finansijski obracun.
9. Nikad ne izmisljati rezultate, minute, poene ni status meca kada
   izvor nije dostupan. Privremeni prekid ESPN-a ne smije izbrisati vec
   potvrden konačni rezultat.
10. Dnevne liste za pripremu se ciste pri prelasku u novi dan,
    dok se aktivni tiketi cuvaju dok se svaki par ne zakljuci.

## Tehnicki vlasnici

- `.github/workflows/memarasix-live-scores.yml` i `sync_live_scores.py`
  prate A/B/C, `nba_live_points.py` prati NBA igrace.
- `.github/workflows/nba-system-live.yml` i `nba_system_live.py` prate
  odvojeni NBA sistem.
- `index.html` i `nba-sistem.html` prikazuju najnovije potvrdjene
  informacije, ukljucujuci browser ESPN fallback ako GitHub kasni.
- `settle_virtual_tickets.py` jedini zakljucuje glavnu A/B/C banku.
- Osvjezavanje UI nije dokaz knjizenja novca; settled banka mora biti
  potvrdena u GitHub JSON-u.

Prije svake relevantne izmjene provjeriti Python regresije, JavaScript
sintaksu te da se parovi prate po originalnim ESPN identifikatorima.
