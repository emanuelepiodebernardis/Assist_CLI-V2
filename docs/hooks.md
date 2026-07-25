# Hook di verifica automatica

Assist CLI verifica il codice quando gli viene chiesto esplicitamente
(`assist verify <file>`). Ma il momento in cui un bug entra nel
codice non è quello in cui qualcuno lancia un comando a mano: è il
momento in cui il codice viene *scritto*, spesso da un assistente AI
che genera decine di righe in pochi secondi. Più tempo passa tra la
scrittura e la verifica, più è probabile che quel codice venga letto,
riusato o buildato sopra prima che qualcuno si accorga che è rotto.

Per questo Assist CLI offre due meccanismi che agganciano `assist
verify` **al momento della scrittura**, invece di lasciarlo come
passo manuale successivo.

## I due meccanismi

### 1. Hook Git `pre-commit` (universale)

Uno script installato in `.git/hooks/pre-commit` che, ad ogni
tentativo di commit, raccoglie i file Python in staging e li passa a
`assist verify` uno per uno. Se anche un solo file fallisce, il
commit viene bloccato (exit diverso da 0) e va corretto prima di
poter procedere.

Questo hook funziona **indipendentemente dall'editor o dall'IDE**
usato per scrivere il codice: agisce a livello di Git, non di
editor. È il meccanismo consigliato se il team usa editor diversi
(VS Code, PyCharm, Vim, Cursor, ecc.) e si vuole una garanzia unica
valida per tutti.

### 2. Hook `PostToolUse` di Claude Code

Una voce nel file `.claude/settings.json` che dice a Claude Code di
eseguire `assist verify` automaticamente subito dopo ogni uso degli
strumenti `Edit` o `Write` su un file. Il report viene generato in
formato markdown e mostrato nella sessione, così un'eventuale
regressione introdotta dal codice generato dall'AI viene segnalata
**in pochi secondi**, non al prossimo commit.

Questo meccanismo è specifico di Claude Code: se il codice viene
scritto da un altro assistente o direttamente a mano, non scatta.
Per questo va usato **in aggiunta** al pre-commit, non al suo posto.

## Installazione

Entrambi gli hook si installano con le funzioni in
`assist/verification/hook_install.py`:

```python
from assist.verification.hook_install import (
    install_pre_commit,
    install_claude_code_hook,
)

install_pre_commit(".")        # scrive .git/hooks/pre-commit
install_claude_code_hook(".")  # scrive/aggiorna .claude/settings.json
```

oppure, quando sarà disponibile il comando CLI dedicato:

```bash
assist install-hooks --pre-commit --claude-code
```

L'installazione dell'hook `pre-commit` fallisce con un errore chiaro
se:

- la directory indicata non è un repository Git (manca `.git`);
- esiste già un hook `pre-commit` che **non** è stato generato da
  Assist CLI (riconosciuto da un marker interno). In questo caso lo
  script non viene sovrascritto: va integrato a mano, aggiungendo la
  chiamata a `assist verify` all'hook esistente.

L'installazione dell'hook Claude Code, invece, fa il **merge** con un
eventuale `.claude/settings.json` già esistente: le chiavi presenti
(incluse quelle non legate agli hook, come `model`) vengono
conservate, e l'hook non viene duplicato se richiamato più volte.

## Comportamento

- **Pre-commit**: se un file fallisce la verifica (verdetto `fail`),
  il commit viene bloccato finché il problema non è risolto o il
  file non è escluso via `.assist.yaml` (vedi
  `assist/verification/repo_config.py`). Un verdetto `warn` non
  blocca il commit.
- **Claude Code**: il verdetto viene mostrato come report, ma non
  impedisce a Claude Code di continuare la sessione: è un segnale
  immediato per l'utente e per il modello, non un blocco rigido come
  il pre-commit.

## Nota per gli utenti Cursor

Cursor non ha un hook `PostToolUse` equivalente a quello di Claude
Code. Per gli utenti Cursor (o qualunque altro editor/IDE) il
meccanismo da usare è **l'hook Git `pre-commit`**: essendo legato al
repository e non all'editor, funziona allo stesso modo qualunque sia
lo strumento con cui il codice è stato scritto o generato.
