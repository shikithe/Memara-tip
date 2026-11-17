# MEMARASIX — NBA tiket C: autonomni AI Scout

**Aktuelni način rada od 17.11.2026.** Zamjenjuje prethodnu zavisnost od GitHubovog ESPN kolektora i međulista. Korisnik je izričito odobrio svakodnevni autonomni izbor i objavu bez potrebe da je online.

## Nadležnosti i raspored

- **ChatGPT automatizacija** `MEMARA C — autonomni NBA Scout`, 17:00 `Europe/Sarajevo`, jeste **jedini istraživač i autor odobrenja**.
- ChatGPT pri izvršenju direktno pretražuje trenutni ESPN raspored, identitete igrača, javne kladioničarske ponude i statistiku.
- **Jedini izvor tačnih NBA player-points linija i kvota je BetSharp:** https://betsharp.com/nba/props?m=points . ESPN i drugi mediji se koriste SAMO za raspored, identitete, povrede i statističku analizu. Ne preuzimaj kvote s Basketball Sphere, LineSmart, HaterPicks ili drugog sajta, jer se različite granice mogu pomiješati. BetSharp obuhvata narednih 48h; Scout obavezno filtrira samo naredna **24h od stvarnog izvršavanja**.
- **Konzistentna kotacija:** ne spajaj `Best over` i `Best under` jer mogu biti za različite granice i bookmakere. Za jednog igrača odaberi jedan bookmaker red/kolonu s jednom istom granicom i obje odgovarajuće Over/Under cijene. Prioritet DK, zatim FD, MGM, drugi validni stupci. Ne tretirati BetSharp javnu indikativnu kvotu kao potvrđenu u stvarnoj sesiji kladionice.
- **Obavezan kvantitativni izvještaj:** ukupan broj rasporedom potvrđenih utakmica u naredna 24h; broj različitih igrača na BetSharpu iz tih utakmica; broj s valjanim dvosmjernim linijama; broj predfiltriranih i broj detaljno analiziranih finalista. Ako broj nije provjeren, reci da nije poznat, nikad ga ne izmišljaj.
 **Ne zavisi** od GitHub fajlova `collector-output/nba-next-24h.json`, `nba-analysis-ready.json`, `nba-player-points.json`, `nba-public-points-offers.json` niti od njihovog vremena osvježavanja.
- **Rolling prozor 24h:** prihvatljive su samo NBA utakmice čiji je provjereni početak **nakon trenutka analize i najkasnije 24 sata poslije**; neposredno prije odobrenja provjeri da utakmice tek počinju, najmanje 20 minuta u budućnosti, i da su unutar naredna 24 sata. Lokalni kalendarski dan nije zamjena za rolling prozor.
- Za tiket C se u GitHub **ne spremaju sirovi rosteri, prikupljene kvote, shortlist, Scout audit niti međufajlovi**. Jedini ulaz u GitHub je završni `memarasix-1455-approved.json` sa tačno dva odobrena igrača.
- `.github/workflows/memarasix-scheduled-publication.yml` prima `push` tog fajla i izvršava `memarasix_approval_gate.py` / `memarasix_1455_publish.py` **isključivo kao tehnički izdavač**: kontrola strukture, datuma, početka utakmica, duplikata, kvota, budžeta; objava u `data.json` i status u `memarasix-1455-audit.json`. GitHub **nikada ne bira igrače i ne ispravlja AI analizu**.
- Stari `memarasix-c-unified.yml` ESPN kolektor ostaje dostupan samo za **ručno dijagnostičko pokretanje**, bez rasporeda ili automatskog okidanja. Drugi workflowi koji služe različitim funkcijama MemaraSix ne predstavljaju uslov za tiket C.

## Scout provjera u samom AI izvršenju

1. Utvrdi provjerene buduće NBA mečeve i ESPN event/player ID-eve za naredna 24h; filtriraj neaktivne i već započete mečeve.
2. Pretraži svježa tržišta **poeni igrača**, oba smjera `over`/`under`, sa **tačnom granicom** i odgovarajućom **pojedinačnom kvotom**; preferiraj izvor kladionice, a kod uporednog sajta naznači da je referentna cijena. Ne izmišljaj drugu stranu tržišta, datume ili svježinu kvota. Upari s provjerenim igračima i mečevima.
3. Procijeni provjereno dostupne kandidate posljednjih 5–10 nastupa, minutažu, trend u odnosu na stvarnu granicu, sezonu i rizike; za najbolje dodatno provjeri povrede/izostanke, protivničku odbranu i tempo, domaće/gostujuće i H2H kada podaci postoje. Oba smjera su dozvoljena, kvota preferirano oko 1,70–1,90.
4. Izaberi **tačno dva različita igrača** samo ako postoje valjane linije, izvori, identitet i dovoljno dobar obrazloženi izbor. Ako nema odgovarajuća dva, preskoči tiket umjesto izmišljanja podataka. Nema garancije ishoda.
5. Provjeri da C nije već odobren/objavljen isti lokalni dan i da bankovni obračun od prethodnog dana dopušta novi tiket. Zatim upiši **samo** `memarasix-1455-approved.json`, sadržaja `date`, `approval_source=chatgpt_ai_analyst`, `approved_at_utc`, `publication_allowed=true`, `tickets=[{id:C,analysis,matches:[...2]}]`. Svaka stavka ima `player_id`, `espn_event_id`, `player`, `team`, `opponent`, `start_utc`, `market=player_points`, `pick`, `points_line`, `odd`, `bookmaker`, `source` (URL).
6. Provjeri stvarnu tehničku objavu u `data.json`, `memarasix-1455-audit.json` i GitHub Actions. Ako publisher zakaže, prijavi tačan kvar; nemoj duplirati tiket.

## Granice

Automatizacija u 17:00 nije garancija početka izvršavanja u tačnoj sekundi; online izvori mogu biti nedostupni. Rezultat je virtuelni tiket prikazan na MemaraTip sajtu, bez ikakve stvarne uplate u kladionici. Ne mijenjati nezavisne tikete A/B i druge dijelove projekta.
