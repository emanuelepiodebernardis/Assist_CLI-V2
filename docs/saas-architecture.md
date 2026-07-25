# Architettura SaaS — GitHub App (Fase 3)

Questo documento descrive il design proposto per trasformare Assist Proof
Engine da CLI locale/CI a servizio SaaS multi-tenant: una GitHub App che
verifica le pull request di piu' organizzazioni clienti, senza che il
cliente debba gestire chiavi API o infrastruttura propria.

E' un documento di design, non implementazione: nessuna delle componenti
qui descritte esiste ancora nel repository. Riprende ed espande la voce
di ROADMAP.md, Fase 3: "GitHub App SaaS (webhook PR, coda di verifica,
dashboard)" e "Sandbox containerizzata (Docker/gVisor) per codice non
fidato".

---

## Perche' non basta la GitHub Action attuale

La GitHub Action documentata in `docs/github-action.md` gia' oggi esegue
`assist verify --diff` su ogni PR e pubblica un commento. Funziona, ma
richiede al cliente di:

- gestire il proprio secret `ANTHROPIC_API_KEY` per ogni repository;
- eseguire codice non fidato (quello della PR) sul runner CI del cliente,
  con lo stesso isolamento a processo usato in locale (`SandboxRunner`,
  vedi nota nel codice: "sufficiente per codice proprio/di fiducia in
  locale");
- installare/aggiornare il workflow YAML manualmente in ogni repo.

La GitHub App sposta l'esecuzione (e l'isolamento del codice non fidato)
fuori dal perimetro del cliente, dentro un'infrastruttura gestita con
sandboxing piu' forte, billing centralizzato e una dashboard.

---

## Schema architetturale

```
                    GitHub (repo del cliente)
                            |
                   evento webhook PR
              (opened / synchronize / reopened)
                            |
                            v
                +------------------------+
                |   GitHub App (webhook  |
                |   receiver, firma      |
                |   HMAC verificata)     |
                +------------------------+
                            |
                            v
                +------------------------+
                |     API gateway         |
                | - valida installazione  |
                | - autentica come App    |
                |   (JWT -> installation   |
                |   token, scope minimo)  |
                | - crea record "verifica"|
                | - enqueue job            |
                +------------------------+
                            |
                            v
                +------------------------+
                |  Coda (Redis / SQS)     |
                |  1 job = 1 file o 1     |
                |  diff-target da         |
                |  verificare              |
                +------------------------+
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
        +----------+  +----------+  +----------+
        |  Worker  |  |  Worker  |  |  Worker  |   (pool orizzontale,
        |  pool    |  |  pool    |  |  pool    |    autoscaling su
        +----------+  +----------+  +----------+    profondita' coda)
              |
              v
     +--------------------------+
     | Sandbox containerizzata   |
     | (Docker/gVisor)           |
     | --network=none            |
     | limiti cpu/mem, timeout   |
     | VerificationPipeline      |
     | (stessa libreria della    |
     |  CLI: sandbox, mutation,  |
     |  judge, fix loop)         |
     +--------------------------+
              |
              v
     +--------------------------+       +----------------------+
     | Commento PR (GitHub API) | ----> | Certificato firmato   |
     | formato pr-comment,      |       | scaricabile           |
     | update idempotente       |       | (per-org signing key) |
     +--------------------------+       +----------------------+
              |
              v
     +--------------------------+
     | Store risultati (DB)     |
     | verifiche, certificati,  |
     | telemetria per repo      |
     +--------------------------+
              |
              v
     +--------------------------+
     | Dashboard (minima)       |
     | storico verifiche,       |
     | mutation score nel tempo |
     | per repo/organizzazione  |
     +--------------------------+
```

---

## Componenti

### GitHub App (webhook PR)

Riceve gli eventi `pull_request` (opened, synchronize, reopened) via
webhook firmato. Non esegue mai codice del cliente in questo processo:
si limita a validare la firma, risolvere l'installazione e mettere in
coda il lavoro. Autentica verso l'API di GitHub come App (JWT ->
installation access token), con lo scope minimo necessario: lettura del
contenuto del repo e scrittura dei commenti sulla PR.

### API gateway

Riceve il job dalla GitHub App, crea il record di "verifica" nel database
(stato `queued`) e lo mette in coda. E' il punto in cui si applicano i
controlli di piano (quota mensile, rate limit per installazione) prima di
consumare risorse di calcolo o chiamate LLM.

### Coda (Redis / SQS)

Disaccoppia la ricezione del webhook (che deve rispondere in pochi
secondi a GitHub) dall'esecuzione effettiva, che puo' richiedere decine
di secondi per file (si vedano le durate reali nel benchmark, 0.5-2s per
caso di test ridotto: su repository reali con piu' mutanti e chiamate LLM
il tempo per file sale). Un job in coda corrisponde a un file Python
target (stessa unita' di lavoro di `assist verify --diff` in locale).

### Worker pool con sandbox containerizzate

Ogni worker esegue la stessa `VerificationPipeline` gia' usata dalla CLI,
ma dentro un container isolato invece che nel sottoprocesso Python del
`SandboxRunner` locale. Requisiti minimi per codice non fidato lato SaaS:

- runtime Docker o gVisor (isolamento kernel aggiuntivo rispetto a un
  container Docker standard, riduce la superficie di attacco su syscall);
- `--network=none`: nessun accesso di rete dal codice/test eseguiti,
  cosi' un test malevolo non puo' esfiltrare dati ne' contattare host
  esterni;
- limiti cpu/mem per container e timeout per esecuzione (estensione
  containerizzata dell'attuale `SandboxRunner`, che oggi ha gia' timeout
  a livello di processo ma isolamento debole, adeguato solo a codice
  proprio eseguito in locale);
- filesystem del container effimero e distrutto ad ogni job, nessun
  volume persistente condiviso tra job diversi.

Il worker pool scala orizzontalmente in base alla profondita' della coda.

### Commento PR e certificato scaricabile

A fine pipeline il worker pubblica (o aggiorna, come gia' fa la GitHub
Action) un commento sulla PR nel formato `pr-comment` esistente
(`assist/verification/pr_comment.py`), e genera un certificato di
verifica firmato (stessa struttura di `assist/verification/certificate.py`,
payload + firma HMAC-SHA256), reso disponibile per il download dal
commento o dalla dashboard.

### Dashboard minima

Vista per organizzazione/repository con: storico delle verifiche (una
riga per PR/commit verificato, verdetto, mutation score), andamento del
mutation score nel tempo (serie storica per repo, per capire se la
qualita' dei test sta migliorando o peggiorando) ed elenco certificati
scaricabili. Niente di piu' nell'MVP: nessuna configurazione via UI nella
prima versione (resta `.assist.yaml` nel repo, come oggi).

---

## Modello dati essenziale

```
installazione (installation)
  id
  github_installation_id
  organizzazione (nome, piano)
  data_creazione
  stato (attiva / sospesa)

repo
  id
  installazione_id (fk)
  nome_completo (org/repo)
  configurazione_effettiva (cache di .assist.yaml risolto)
  ultima_verifica_at

verifica (verification_run)
  id
  repo_id (fk)
  pull_request_number
  commit_sha
  file_target
  verdetto (pass / warn / fail)
  mutation_score
  evidenze (jsonb: stessa struttura di EvidenceBundle/VerificationOutput)
  durata_secondi
  costo_stimato (chiamate fast/strong contate)
  creata_at

certificato (certificate)
  id
  verifica_id (fk)
  payload (jsonb, stessa struttura di CertificatePayload)
  firma
  chiave_org_id (fk verso la chiave di firma usata)
  creato_at
```

`verifica` ed `evidenze` ricalcano deliberatamente `VerificationOutput` e
`EvidenceBundle` gia' definiti in `assist/verification/evidence.py`: la
persistenza SaaS e' una serializzazione di strutture che la pipeline
produce gia' oggi, non un modello dati nuovo da progettare da zero.

---

## Sicurezza

- **Il codice del cliente non tocca mai l'LLM se non nelle porzioni
  necessarie.** Solo il codice del file target (e, se serve contesto,
  gli import locali raccolti da `DependencyCollector`) entra nel prompt
  per la generazione dei test boundary e per il giudizio finale. Il
  verdetto pass/warn/fail resta calcolato da evidenza deterministica
  (sandbox + mutation testing) prima e indipendentemente da qualunque
  chiamata LLM, come nella pipeline locale.
- **Sandbox senza rete.** Ogni esecuzione di codice/test cliente avviene
  in un container con `--network=none`: nessuna via di uscita per dati o
  di ingresso per dipendenze non dichiarate.
- **Retention configurabile.** Codice sorgente ed evidenze grezze hanno
  un periodo di retention configurabile per organizzazione (default
  breve, es. 30 giorni); i certificati firmati, che contengono solo un
  hash sha256 del sorgente e non il sorgente stesso, possono avere
  retention piu' lunga per finalita' di audit.
- **Firma dei certificati con chiave per-organizzazione.** Ogni
  organizzazione cliente ha una propria chiave di firma HMAC-SHA256
  (estensione multi-tenant dell'attuale variabile singola
  `ASSIST_SIGNING_KEY`), cosi' un certificato e' verificabile solo con la
  chiave della organizzazione che lo ha prodotto e una chiave compromessa
  non espone i certificati di altri clienti.
- **Isolamento tra tenant.** Nessun dato (codice, evidenze, certificati)
  di un'installazione e' raggiungibile dai worker o dalle query di
  un'altra installazione: ogni riga del modello dati e' partizionata per
  `installazione_id`.

---

## Costi per verifica

Split fast/strong gia' presente nella pipeline (`config/settings.yaml`,
sezione `models`: fast = `claude-haiku-4-5`, strong = `claude-sonnet-4-6`):

- **Generazione test boundary (fast)**: ~1 chiamata per file verificato,
  volume alto, costo per chiamata basso (tier haiku).
- **Giudizio del verdetto + eventuale fix (strong)**: 1 chiamata per la
  spiegazione del verdetto, piu' fino a 3 iterazioni aggiuntive nel
  `ValidatedFixLoop` solo quando il verdetto e' `fail` (1-4 chiamate
  strong totali per file, in pratica quasi sempre verso il lato basso
  perche' la maggior parte dei file non e' in `fail`).
- **Mutation testing: gratuito lato LLM.** E' CPU only: gli AST mutator
  generano varianti del sorgente e le eseguono in sandbox, nessuna
  chiamata a modello coinvolta. E' anche la fase piu' pesante in tempo
  macchina (fino a `max_mutants` esecuzioni pytest per file, oggi 40 di
  default), ma il suo costo marginale e' compute, non token.

Il costo per verifica scala quindi con: 1 chiamata fast (quasi sempre) +
1-4 chiamate strong (quasi sempre 1) + tempo CPU per il mutation testing.
La voce dominante sul costo monetario e' la parte LLM; la voce dominante
sul tempo di attesa e' il mutation testing. Il target dichiarato in
ROADMAP.md e' un costo per verifica sotto $0.05 con questo split.

---

## Pricing proposto

- **Free per progetti open source.** Nessun costo per repository pubblici:
  e' il canale di distribuzione naturale per uno strumento di
  verifica — lo stesso posizionamento delle GitHub Action gratuite per
  OSS di strumenti comparabili.
- **Team: $20-30/dev/mese.** Include verifiche illimitate (entro una
  quota ragionevole), dashboard, certificati scaricabili, retention
  standard.
- **Enterprise.** Audit trail esteso (retention lunga configurabile,
  export dei certificati in blocco), SSO per l'accesso alla dashboard,
  chiave di firma dedicata per organizzazione, eventuale supporto a
  deployment on-prem del worker pool per chi non puo' far uscire il
  codice dal proprio perimetro di rete.

---

## MVP SaaS in 4-6 settimane

Cosa entra:

- GitHub App con webhook PR e commento (riuso diretto di
  `pr_comment.py` e della logica gia' esistente in
  `.github/workflows/assist-verify.yml`, portata da workflow YAML a
  servizio);
- coda singola (Redis e' sufficiente per l'MVP, SQS solo se si parte
  gia' su AWS) e un solo worker pool, senza priorita' per piano;
  autoscaling minimo o assente all'inizio;
  sandbox Docker (senza gVisor: livello di isolamento accettabile per un
  MVP con clienti onboardati manualmente, gVisor si aggiunge quando si
  apre l'accesso self-service a repository sconosciuti);
- store risultati e certificati (una tabella `verifica`, una
  `certificato`, niente di piu' granulare);
- dashboard minima: solo lista verifiche per repo, nessun grafico di
  andamento nella prima versione;
- un solo piano a pagamento (team), free per OSS deciso a mano
  (allowlist), enterprise gestito come vendita diretta senza feature
  differenziate nel codice.

Cosa si taglia consapevolmente:

- nessun self-service completo di billing (fatturazione gestita a mano
  o con un provider esterno collegato manualmente, non integrata nel
  flusso di onboarding);
- nessun grafico storico del mutation score nella dashboard (si mostra
  solo l'ultimo valore per repo, la serie storica arriva dopo);
- nessun supporto multi-linguaggio (resta solo Python, coerente con lo
  stato attuale della CLI: il secondo linguaggio e' un item separato di
  ROADMAP.md, non nello scope dell'MVP SaaS);
- nessun SSO ne' audit trail esteso (riservati al piano enterprise, non
  costruiti finche' non c'e' un cliente enterprise reale);
- gVisor rimandato: si parte con isolamento Docker standard e
  `--network=none`, sufficiente per un numero limitato di clienti
  onboardati manualmente e verificati, non ancora per accesso pubblico
  self-service.

L'obiettivo dell'MVP e' validare che il flusso webhook -> coda -> sandbox
-> commento PR regga in produzione con clienti reali, riusando quanto
piu' possibile la `VerificationPipeline` gia' esistente e testata (294
test) invece di riscriverla per il contesto SaaS.
