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
