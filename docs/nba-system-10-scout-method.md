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

## NAJNOVIJE PRAVILO 21.11.2026. — KVALITET PODATAKA ODREĐUJE KVALITET ANALIZE

1. **Prvi prolaz**: pretraži ESPN za svakog člana grupe, strogo od prvog do posljednjeg. Ako za igrača nema statistike, zabilježi i pređi na sljedećeg. NEMA zaustavljanja posla.
2. **Drugi prolaz**: za igrače sa nedostajućim podacima provjeri nezavisan drugi izvor. Ako sekundarni izvor takođe ne daje traženi podatak, zabilježi `not_verified` i nastavi dalje. Ne traži puni L5 po svaku cijenu.
3. **Rangiranje SVIH**: za svakog upiši sve zaista pronađene game log zapise (0–5), sezonu, matchup, povrede i izvore gdje je moguće. Nema fabrikovanja. Procjena i numerički `score` su proporcionalni dokazima, a posebno zabilježi `confidence:0..100` — malo podataka znači *nižu pouzdanost*, a ne automatsku diskvalifikaciju. Ako nema osnova za preciznu vjerovatnoću, `estimated_probability:null`; nikada ne izmišljaj broj.
4. Odaberi najbolje dvije opcije uz uvažavanje kvaliteta i količine dokaza, procijenjene prednosti u odnosu na kvotu i sportskog rizika. Smiju imati manje od 5 potvrđenih utakmica ako su drugi dostupni dokazi korisni; jasno objasni ograničenja. U auditu `ranking` i dalje moraju biti svi M originalni kandidati.
5. **Objava traži stvarno potvrđene podatke koji su neophodni za konkretan tip**: pravi ESPN player ID i event ID, tačan budući start, granicu, obje postojeće kvote (jedinstveni odabrani bookmaker), identitet i status nastupa. Ako takva dva kandidata ne postoje, prijavi stvarni razlog blokade. Ako ima ih dva, nepotpuna statistika ostalih ne blokira tiket.
6. GitHub `nba_system_pipeline.py` ne donosi sportske odluke, već čuva izvorni redoslijed, sprečava izmišljene identitete/kvote i preskakanje grupa; ova metoda se primjenjuje na **svih deset** cikličkih grupa.

**Ovo pravilo ima prednost nad ranijim tvrdnjama da svi kandidati ili oba izabrana moraju imati kompletan petomečni game log.** Nikad ne označavaj izmišljene informacije kao potvrđene.

## Izvršni workflow — implementirano 20.11.2026.

- `nba_system_pipeline.py` je **strogi kontrolor** koji ne bira tipove. Provjerava datirani zamrznuti originalni snapshot, 10 matematički uravnoteženih grupa, **tačno sva M člana** svake rang-liste, ocjene, izvore, prethodnih 5 utakmica sa minutažom, objasnjenja matchupa/povreda i obavezne dvije najbolje rangirane opcije; ne dopušta objavu ako je meč počeo ili bilo šta preskočeno.
- Za novi datum Scout sprema `collector-output/nba-system-offer-YYYY-MM-DD.json` sa `frozen:true`, `original_snapshot_exact:true` (samo ako je izvor stvarno preuzet prije prve objave), `date`, `captured_at_utc`, `source`, `bookmaker` i `offers` listom sa ESPN ID-evima, datumima mečeva, oba ponuđena decimalna oddsa i granicom poena. Broj i redoslijed kandidata se nikad ne mijenjaju tokom ciklusa.
- Za svaku grupu AI Scout priprema `collector-output/nba-system-scout-YYYY-MM-DD-group-N.json` sa `ranking` od 1 do M i `selected_player_ids` prva dva rangirana. Datoteka je potpun samostalan revizijski trag, ne samo imena dva izabrana.
- Kada Scout audit bude upisan na GitHub, `.github/workflows/nba-system-scout-publish.yml` **automatski provjerava i objavljuje samo prvi još neobjavljen tiket** pomoću `python nba_system_pipeline.py publish --date YYYY-MM-DD`. Ako kandidat/izvor nedostaje, workflow završava greškom i ne mijenja `nba-sistem.json`.
- AI u **istom aktivnom izvršavanju** odmah nakon potvrde objave nastavlja istraživanje naredne grupe. GitHub workflow objavljuje i provjerava, ali **ne može sam pokrenuti novo ChatGPT AI istraživanje** ako je AI izvršavanje već završeno; za to je potreban odvojen stvarni AI okidač.
- Prethodni NBA settlement workflow i publisher koriste isti concurrency lock `nba-system-ledger` radi smanjenja sukoba.
- `.github/workflows/nba-system-scout-ci.yml` automatizovano provjerava 7 Python testova: uravnoteženje, originalni snapshot, puni rang, izbor top 2, zabranu preskakanja, idempotentno stanje i uzastopnu objavu.
- **Stari ciklusi ostaju neizmijenjeni**, uključujući 20.11.2026, koji nije prethodno prošao ovu strožu kontrolu.
