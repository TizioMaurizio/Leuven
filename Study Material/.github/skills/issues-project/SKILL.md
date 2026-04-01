---
name: issues-project
description: Crea issue mancanti e organizza un GitHub Project per fase (campo Phase + grouping nella view).
---

## User Input

```text
$ARGUMENTS
```

## Goal

Partendo da `tasks.md` (o da `functional-analysis.md` se non c'è tasks), creare issue non duplicate e predisporre il progetto GitHub con organizzazione per fase.

## Prerequisiti

- Repository con remote GitHub valido.
- Accesso GitHub con permessi issue/project.
- Se usi CLI `gh`: token con scope `project`.

## Procedura

1. **Risolvi repository target**
   - Leggi `remote.origin.url`.
   - Procedi solo se il remote è GitHub e owner/repo corrispondono al progetto corrente.

2. **Sorgente issue**
   - Se esiste `specs/<feature-id>/tasks.md`, usa quello.
   - Altrimenti usa `specs/<feature-id>/functional-analysis.md` e deriva issue per requisito FR/NFR.

3. **Crea issue senza duplicati**
   - Per ogni item, genera titolo stabile con prefisso fase, es. `[Fase 1] ...`.
   - Cerca issue aperte simili per titolo.
   - **Crea issue** se non trovi una issue equivalente per stesso obiettivo/fase.
   - **Aggiorna issue esistente** (invece di crearne una nuova) se esiste già e manca parte di: acceptance criteria, dipendenze, fase, contesto.
   - **Non aggiornare** issue già chiusa/completata, salvo richiesta esplicita dell'utente.
   - Inserisci nel body: contesto, obiettivo, acceptance criteria, dipendenze.
   - Nel body includi sempre una riga standard:
      - `Depends on: #<issue>, #<issue>` oppure `Depends on: none`

4. **Template body issue (obbligatorio)**

```md
## Context
<perché serve>

## Objective
<risultato atteso>

## Acceptance Criteria
- [ ] ...
- [ ] ...

## Dependencies
Depends on: #12, #34

## Notes
Phase: Fase 1
```

5. **Crea o riusa GitHub Project**
   - Se esiste un project per la feature, riusalo.
   - Se non esiste, creane uno con titolo della feature.

6. **Configura organizzazione per fase**
   - Verifica campo `Phase` nel project (single select).
   - Se manca, crealo con opzioni minime: `Fase 1,Fase 2,Fase 3,Backlog`.
   - Aggiungi tutte le issue al project.
   - Imposta il valore `Phase` per ogni issue in base alla fase d'origine.

7. **View per fase**
   - Crea (o riusa) una view `By Phase` del progetto e imposta grouping sul campo `Phase`.
   - Se l'automazione API/CLI della creazione view non è disponibile nell'ambiente, apri il project sul web e completa i passaggi UI documentati, poi conferma risultato.

## Output minimo da restituire

- Elenco issue create (numero + titolo).
- Elenco issue riusate (già esistenti).
- Project usato/creato (nome + URL).
- Conferma view `By Phase` attiva e raggruppata per `Phase`.
- Dipendenze dichiarate per ogni issue nel formato `Depends on:`.

## Riferimenti web (base operativa)

- VS Code custom agents (`.agent.md`, frontmatter e tools):
  - https://code.visualstudio.com/docs/copilot/customization/custom-agents
- GitHub custom instructions e file repository-level:
  - https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- GitHub Projects table grouping by field:
  - https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-table-layout
- GitHub CLI project commands:
  - https://cli.github.com/manual/gh_project
  - https://cli.github.com/manual/gh_project_field-create
  - https://cli.github.com/manual/gh_project_item-add
  - https://cli.github.com/manual/gh_project_item-edit
