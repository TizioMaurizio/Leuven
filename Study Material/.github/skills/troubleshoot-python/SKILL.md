---
name: troubleshoot-python
description: Workflow per diagnosticare e risolvere bug Python (runtime, import, I/O, dipendenze) con root cause analysis.
argument-hint: "Es: 'Errore runtime in script X' o 'ImportError in modulo Y'"
compatibility: Python projects with runtime bugs or environment issues.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: Python
  type: troubleshooting
  languages: [Python]
---

# Troubleshooter Python

Usa questa skill per eccezioni runtime Python, problemi di import, mismatch ambiente, errori I/O o regressioni logiche in servizi/script.

## Obiettivo

- Riprodurre l’errore nello stesso contesto di esecuzione.
- Distinguere problema di codice da problema di ambiente.
- Applicare fix minimale e verificabile.

## Workflow

1. Riproduci con contesto completo
   - Raccogli comando, versione Python, env attivo, traceback completo.
   - Se manca il traceback completo, richiedilo prima di modificare codice.

2. Classifica il problema
   - `ImportError`/`ModuleNotFoundError` -> dipendenze o path.
   - `TypeError`/`AttributeError` -> contratto oggetti non rispettato.
   - Errori I/O/config -> path, permessi, variabili ambiente.

3. Isola root cause
   - Riduci a caso minimo riproducibile.
   - Verifica ipotesi con test/comando mirato.

4. Applica fix
   - Correggi il punto di rottura reale, non i soli sintomi.
   - Mantieni compatibilità con convenzioni esistenti del repository.

5. Valida
   - Esegui test mirati o comando che prima falliva.
   - Se opportuno, esegui una verifica più ampia non distruttiva.

6. Report finale
   - Root cause, file aggiornati, comandi di verifica, limiti noti.

## Check rapidi

- Ambiente/venv corretto?
- Dipendenze dichiarate vs usate?
- Gestione errori esplicita nei punti I/O?
- Tipi e contratti funzione coerenti?

## Riferimenti

- Allineata ai pattern pratici in `github/awesome-copilot` per debug iterativo e verifiche incrementali.
