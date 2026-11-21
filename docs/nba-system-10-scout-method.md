# NBA SISTEM — OBAVEZNI SCOUT ZA SVIH 10 GRUPA

Pravilo potvrđeno 20.11.2026. Koristi se za svaki NAREDNI ciklus NBA desetke. Ovo je **obavezan kriterij prije objave**, a ne opcionalna preporuka. Ne mijenja retroaktivno objavljene tikete od 20.11.

## Osnovni slijed

1. Prije prve analize sačuvaj **cijelu** izvornu BetSharp NBA points ponudu kao datirani, fiksni snapshot: svi kvalifikovani igrači redom s ESPN player_id, mečem, marketom, granicom i kvotama iz jedne konzistentne kladioničarske kolone, izvorom i vremenom očitavanja. Ako originalni snapshot nije sačuvan, ne glumi da je rekonstruisan izvorni redoslijed.
2. Rasporedi ukupni broj N u **tačno 10 uzastopnih grupa**: veličina floor(N/10), prvih N%10 grupa ima +1. Bez ponovne podjele ili promjene redoslijeda nakon objave prve grupe.
3. **Svaku grupu obradi kao onu prvu tabelu 1–15:** za **svakog** člana napravi pun pojedinačni Scout prije rangiranja i objave. Nema prečica, unaprijed izabranih favorita ili pregleda samo odabrane dvojice.
4. Za svakog kandidata zabilježi: tim i protivnika; tačan termin; obje ponuđene granice/kvote i odluku OVER ili UNDER; posljednjih 5 nastupa s poenima, minutama i prolazima na toj granici; sezonu i home/away učinak; do 5 relevantnih H2H utakmica; protivničku odbranu na poziciji i direktnog čuvara ako pouzdano dostupan; povrede, izostanke, očekivanu minutažu i ulogu; rizike i **procijenjenu vjerovatnoću prolaza sa objašnjenjem metodologije** (ne izmišljati tačan procenat). Svaki podatak poveži s izvorom i datumom. Nepoznato označi **nije potvrđeno**.
5. Po završetku **svih članova grupe**, napravi **cijelu rang-listu 1–M**, sa ocjenama, sažetim razlozima i poređenjem realne vjerovatnoće naspram ponuđene kvote. Sačuvaj i rangiranje onih koji nisu izabrani, ne samo dvojicu.
6. Izaberi **dva najjača obrazložena tipa** iz grupe: različiti igrači, pouzdana linija i kvota, netaknuti mečevi, zdravstveni/minutažni rizici razmotreni. Ako nema dvije dovoljno potkrijepljene opcije, označi grupu kao **blokiranu** i ne objavljuj fingirani tiket.
7. Prije GitHub objave snimi u zaseban audit kompletan Scout za grupu: originalni kandidati, svih M rangova, podaci po utakmicama, H2H, defanziva, izostanci, kvote/izvori, razloga za dva odabira i nedostaci. Prihvatljiva šema: `collector-output/nba-system-scout-YYYY-MM-DD-group-N.json` s `analysis_complete=true` samo ako su sve stavke pregledane; za nedostupno upiši `not_verified` uz objašnjenje. Bilježi koliko kriterija nije potvrđeno; nepotpunost ne smije biti prikazana kao kompletna dubinska analiza.
8. Tek kada je audit potvrđen i oba tipa validirana, **ODMAH objavi tiket N na GitHubu**, potvrdi commit i očitanje; tek tada **odmah nastavi sljedeću grupu unutar istog izvršavanja**, bez čekanja zakazanog termina. Sačuvaj napredak nakon svake grupe; nikada ne prepisuj objavljeni tiket, ne dupliraj igrača, ne diraj banku C/A/B.
9. Vremensko ograničenje ili nedostupnost izvora **nisu razlog za spuštanje standarda**. Ako izvršavanje mora stati, pošteno prijavi prvi nezavršen korak i nastavi na idućem pokretanju; nikad ne tvrdi da je svih 10 potpuno analizirano ako nisu.

**Prioritet:** ako stariji prompt dozvoljava samo pregled L5 prosjeka ili objavu bez pune rang-tabele, ovaj dokument i nova eksplicitna korisnička instrukcija imaju prioritet.

## PRIORITETNO PRAVILO 21.11.2026. — ESPN prvo kompletan prolaz, pa sekundarni izvori

1. AI Scout prolazi cijelu odabranu grupu **od prvog do posljednjeg igrača na ESPN-u**. Ako je četvrtom igraču game log nedostupan, zapiše nedostatak i **nastavlja na petog**, šestog, sedmog itd. Nepostojanje pojedinačnog podatka nikad ne prekida obradu grupe.
2. Tek kada je obavljen primarni ESPN prolaz svih članova, pravi drugi prolaz **samo za igrače i polja kojima nešto nedostaje** preko dostupnog vjerodostojnog sekundarnog izvora (npr. NBA.com ili provjerljive statističke stranice). Zabilježi oba pokušaja, URL-ove, datum i koje statistike i dalje nedostaju.
3. Svi igrači grupe moraju biti evidentirani u audit rang-listi 1–M. Ako i nakon drugog prolaza pojedinom igraču nedostaje pouzdana L5 statistika, označi ga `eligibility: "insufficient_data"` i `research: {"espn_attempted":true,"secondary_attempted":true,"missing":["..."],"reason":"..."}`, pa ga izuzmi iz izbora. Nije dozvoljeno izmišljati poene, minute, H2H ili procente radi popunjavanja praznina.
4. Ako nakon **oba** prolaza postoje najmanje **dva potpuno provjerena i dovoljno dobra kandidata**, rangiraj ih iznad nepotpunih, odaberi dva najbolje argumentovana tipa, i objavi preko standardnog GitHub validacionog pipelinea. Zadrži nepotpune članove u audit evidenciji s nižim rangom i obrazloženjem.
5. Ako su preostala manje od dva pouzdana tipa, ili su mečevi počeli, ili nema potvrde o nastupu, grupa ostaje blokirana. **Statistička nedostupnost nekih ostalih članova ne blokira objavu dobre dvojice.**
6. Jedna grupa po AI izvršavanju; narednu aktivira samo feedback potvrđene GitHub objave kada postoji nova satna AI provjera, a ne novi cron po pojedinom igraču.

**Napomena implementacije:** GitHub validator `nba_system_pipeline.py` sada dozvoljava `eligibility:"insufficient_data"` samo uz oba evidentirana pokušaja i nedostajuće stavke; dva izabrana člana moraju biti `eligible` sa punim individualnim `last_five`. Ovo pravilo zamjenjuje raniju obavezu da svako od M članova mora imati pet numeričkih game log zapisa.

## Izvršni workflow — implementirano 20.11.2026.

- `nba_system_pipeline.py` je **strogi kontrolor** koji ne bira tipove. Provjerava datirani zamrznuti originalni snapshot, 10 matematički uravnoteženih grupa, **tačno sva M člana** svake rang-liste, ocjene, izvore, prethodnih 5 utakmica sa minutažom, objasnjenja matchupa/povreda i obavezne dvije najbolje rangirane opcije; ne dopušta objavu ako je meč počeo ili bilo šta preskočeno.
- Za novi datum Scout sprema `collector-output/nba-system-offer-YYYY-MM-DD.json` sa `frozen:true`, `original_snapshot_exact:true` (samo ako je izvor stvarno preuzet prije prve objave), `date`, `captured_at_utc`, `source`, `bookmaker` i `offers` listom sa ESPN ID-evima, datumima mečeva, oba ponuđena decimalna oddsa i granicom poena. Broj i redoslijed kandidata se nikad ne mijenjaju tokom ciklusa.
- Za svaku grupu AI Scout priprema `collector-output/nba-system-scout-YYYY-MM-DD-group-N.json` sa `ranking` od 1 do M i `selected_player_ids` prva dva rangirana. Datoteka je potpun samostalan revizijski trag, ne samo imena dva izabrana.
- Kada Scout audit bude upisan na GitHub, `.github/workflows/nba-system-scout-publish.yml` **automatski provjerava i objavljuje samo prvi još neobjavljen tiket** pomoću `python nba_system_pipeline.py publish --date YYYY-MM-DD`. Ako kandidat/izvor nedostaje, workflow završava greškom i ne mijenja `nba-sistem.json`.
- AI u **istom aktivnom izvršavanju** odmah nakon potvrde objave nastavlja istraživanje naredne grupe. GitHub workflow objavljuje i provjerava, ali **ne može sam pokrenuti novo ChatGPT AI istraživanje** ako je AI izvršavanje već završeno; za to je potreban odvojen stvarni AI okidač.
- Prethodni NBA settlement workflow i publisher koriste isti concurrency lock `nba-system-ledger` radi smanjenja sukoba.
- `.github/workflows/nba-system-scout-ci.yml` automatizovano provjerava 7 Python testova: uravnoteženje, originalni snapshot, puni rang, izbor top 2, zabranu preskakanja, idempotentno stanje i uzastopnu objavu.
- **Stari ciklusi ostaju neizmijenjeni**, uključujući 20.11.2026, koji nije prethodno prošao ovu strožu kontrolu.
