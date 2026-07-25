# GitHub Action: verifica automatica delle pull request

Il workflow `.github/workflows/assist-verify.yml` esegue la pipeline
di **Assist Proof Engine** (`assist verify`) su ogni pull request
aperta o aggiornata verso `main`, e pubblica l'esito come commento
sulla PR stessa.

## Cosa fa l'action

1. Fa il checkout del repository con la history completa
   (`fetch-depth: 0`), necessaria per calcolare il diff rispetto al
   branch di base.
2. Installa Assist CLI e le dipendenze (`pip install -e . pytest
   anthropic python-dotenv pyyaml`).
3. Esegue:

   ```bash
   python -m assist.cli.main verify \
     --diff "origin/<base>...HEAD" \
     --provider anthropic \
     --format pr-comment \
     -o /tmp/assist_comment.md
   ```

   verificando solo i file Python effettivamente toccati dalla PR
   (mutando solo le righe cambiate, non l'intero file).
4. Pubblica il report come commento sulla PR. Se un commento di
   Assist esiste gia' (riconosciuto cercando il testo "Assist Proof
   Engine"), viene **aggiornato** invece di crearne uno nuovo ad ogni
   push.
5. Fa fallire il job (quindi il check della PR) solo se il verdetto
   complessivo e' `fail` — un mutation score basso (`warn`) non
   blocca la pipeline, e' solo un segnale visibile nel commento.

## Setup del secret `ANTHROPIC_API_KEY`

L'action usa un provider LLM reale (`--provider anthropic`), quindi
serve una chiave API valida:

1. Nel repository GitHub: **Settings → Secrets and variables →
   Actions → New repository secret**.
2. Nome: `ANTHROPIC_API_KEY`. Valore: la chiave API Anthropic.
3. Nessun'altra configurazione e' richiesta: il workflow la legge
   automaticamente tramite `secrets.ANTHROPIC_API_KEY`.

Senza il secret configurato, lo step di verifica fallira' alle
chiamate LLM (generazione test boundary e spiegazione del verdetto);
il commento pubblicato segnalera' comunque l'errore.

## Come leggere il commento

Il commento generato (vedi `assist/verification/pr_comment.py`) ha
questa struttura:

- **Header**: titolo e riga riassuntiva con i conteggi
  `✅ pass / ⚠️ warn / ❌ fail` sui file verificati.
- **Tabella**: una riga per file, con verdetto, mutation score e
  esito dei test (es. `3 ok` oppure `2 falliti`).
- **Sezioni `<details>`**: una per ogni file non `pass`, con i motivi
  del verdetto, i primi mutanti sopravvissuti (riga, descrizione,
  snippet originale) ed eventuale fix proposto — segnalato come
  "Fix validato in sandbox ✅" se e' stato verificato automaticamente
  in sandbox prima di essere suggerito.
- **Footer**: nota che ricorda che i verdetti derivano da evidenze
  deterministiche (sandbox + mutation testing), non da un'opinione
  dell'LLM.

Se il contenuto supera i limiti di GitHub sui commenti, le sezioni di
dettaglio vengono troncate (header e tabella restano sempre intatti)
e compare la nota "(output troncato)".

## Configurazione per-repo (`.assist.yaml`)

I parametri della pipeline (soglia di mutation score, timeout della
sandbox, numero massimo di mutanti, generazione dei test boundary,
ecc.) sono configurabili per singolo repository tramite un file
`.assist.yaml` nella root del progetto, che sovrascrive i default di
`config/settings.yaml`. Consulta la documentazione di configurazione
del progetto per l'elenco completo delle chiavi disponibili.

## Costi attesi

La pipeline usa due tier di modelli (vedi `config/settings.yaml`,
sezione `models`):

- **fast** (es. `claude-haiku-4-5`): usato in alto volume per
  generare i test sui casi limite (boundary tests) di ogni file
  verificato. Chiamate economiche, una o poche per file.
- **strong** (es. `claude-sonnet-4-6`): usato una sola volta per
  file per spiegare il verdetto e, solo se necessario (verdetto
  `fail`), proporre un fix. Chiamate piu' costose ma a basso volume.

Il costo per PR scala quindi con il numero di file Python toccati
dal diff, non con la dimensione dell'intero repository: la maggior
parte della spesa e' sul tier fast (boundary tests), mentre il tier
strong interviene solo per la spiegazione finale e i fix.
