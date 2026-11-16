# MEMARASIX — stalni Scout postupak za tiket C

Usvojeno 2026-11-16 na izričit zahtjev korisnika. **Analitičar ChatGPT jedini istražuje, rangira i odobrava tiket; GitHub je isključivo tehnički objavljivač.**

## Ulaz i obuhvat
- ESPN `collector-output/nba-next-24h.json` koristi se samo za naredna 24h utakmice, igrače, ID i termine, **ne** za kvote.
- Pronađi svježe javno vidljive kladioničarske/player-prop ponude sa obje strane tržišta: tačan igrač, tačna granica poena i kvota Over/Under, izvor i vrijeme provjere kad su dostupni. Prioritet direktno vidljivoj kladionici (bet365, bet-at-home, Mozzart), a ako to nije čitljivo, uporedni javni izvori uz jasno imenovanog bookmakera.
- Upari **sve** javno pronađene NBA igrače s ESPN listom; ukloni duplikate. Ne pretpostavljaj da svaki ESPN roster igrač ima kladioničarsku ponudu. Ne izmišljaj kvote niti tretiraj statističku granicu kao ponudu bez kvota.
- Za svakog uparenog kandidata zabilježi oba smjera, cijenu i granicu. Predfilter svih kandidata koristi posljednjih 5–10 rezultata, njihov odnos prema granici i sezonu, tako da se prepoznaju i Over i Under kandidati. Označi nedostajuće statistike i rizike.
- Najboljim kandidatima dodatno provjeri minutažu, status nastupa/povreda i očekivanu ulogu, odbranu protivnika po pozicijama, home/away, međusobne susrete, promjene kvote, raspored i moguće ograničenje minutaže.
- Razlikuj učestalost prelaska granice od procijenjene vjerovatnoće: 5/5 ili 8/10 nisu garancija, a kvota implicira prag rentabilnosti. Provjeri odnos rizika i cijene, prioritizuj okvirno 1.70–1.90 kada postoji odgovarajuća vrijednost.
- Izaberi **tačno 2** igrača za tiket C; sačuvaj potpunu selekciju i razloge isključenja drugih finalista u `collector-output/ticket-c-scout-audit-YYYY-MM-DD.json`; pripremi nacrt `collector-output/ticket-c-manual-proposal.json`. Prije odobrenja potvrdi tačne datume/termine i raspoloživost. Cijene bez direktne bookmaker verifikacije označi kao indikativne.
- **Samo ChatGPT analitičar** (nakon korisničkog naloga/odobrenja) upisuje `memarasix-1455-approved.json` sa datiranim odobrenjem i dva igrača. GitHub publisher na push validira samo tehnički ugovor, datume, identitete, početak meča i računicu, pa automatski upisuje `data.json` i objavljuje na landing page. Ne bira, ne dopunjava i ne prepisuje AI odobrenje.
- Nema obaveze čekati Odds API ili automatski kolektor kvota. Fudbal A/B i arhiva se ne mijenjaju kroz ovaj postupak. Sačuvaj banku i dnevne uloge prema postojećim pravilima; samo objavljivanje na sajtu nije uplata tiketa u kladionici.

## Primjer 2026-11-16
Iz 278 ESPN igrača u 8 NBA utakmica, pronađeno 106 jedinstvenih tržišta poena sa javnim kvotama; nakon univerzalnog filtera izabrani Davion Mitchell više 13.5 i Franz Wagner više 21.5. Obje kvote su javne poredbene cijene, ne potvrđena direktna bookmaker ponuda. Detaljan audit: `collector-output/ticket-c-scout-audit-2026-11-16.json`.
