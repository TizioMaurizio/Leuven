---
name: troubleshoot-react
description: Workflow per diagnosticare e correggere bug React/TypeScript (stato, effetti, rendering, eventi) con verifica mirata.
argument-hint: "Es: 'Bug nel componente X' o 'Errore in hook Y'"
compatibility: React/TypeScript projects with frontend bugs.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: React/TypeScript
  type: troubleshooting
  languages: [TypeScript]
---

# Troubleshooter React

Usa questa skill quando il bug riguarda frontend React/TypeScript: regressioni UI, stato incoerente, race condition in `useEffect`, errori runtime in browser, mismatch tra comportamento atteso e reale.

## Obiettivo

- Ottenere una riproduzione affidabile del bug.
- Isolare root cause nel componente/hook corretto.
- Applicare fix minimale con verifica rapida.

## Workflow

1. Riproduci il bug
   - Esegui app o test frontend.
   - Raccogli errore console, stack trace, azioni utente minime.

2. Isola la causa
   - Controlla props/state/effects nel percorso del bug.
   - Verifica dipendenze di `useEffect` e gestione cleanup.
   - Cerca mutazioni non immutabili, chiavi lista instabili, closure stale.

3. Correggi con impatto minimo
   - Tocca solo i file strettamente coinvolti.
   - Evita refactor non necessari nello stesso passaggio.

4. Valida
   - Esegui test mirati della feature.
   - Se bug è visuale/flusso utente, usa Playwright MCP per conferma comportamento.

5. Report finale
   - Root cause, fix, validazione eseguita, rischio residuo.

## Check rapidi

- Stato derivato coerente?
- Side-effect idempotenti?
- Event handler con dati aggiornati?
- Loading/error state gestiti esplicitamente?

## Riferimenti

- Pattern troubleshooting ispirati agli agent debug/workflow di `github/awesome-copilot` (focus su riproducibilità e fix verificabili).
