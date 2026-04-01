---
name: react-unit-test
description: Workflow multi-step per creare unit test React/TypeScript con framework già adottato dal progetto.
argument-hint: "Es: 'Aggiungi unit test per componente X' o 'Copertura test per hook Y'"
compatibility: React/TypeScript projects with existing test framework (vitest, jest) or no tests.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: React/TypeScript
  type: unit testing
  frameworks: [vitest, jest]
  languages: [TypeScript]
---

## User Input

```text
$ARGUMENTS
```

## Goal

Creare/aggiornare unit test React senza cambiare stack di test esistente.

## Bundled assets

- `templates/component.test.template.tsx`

## Workflow

1. Rileva stack test frontend (`vitest`/`jest`, RTL, setup file).
2. Identifica componenti/hooks toccati e casi limite.
3. Crea test da template adattando nomi, fixture e mock.
4. Esegui test mirati (file/suite) e poi eventuale run più ampia.
5. Riporta coverage aggiunta e gap residui.

## Regole

- Preferisci React Testing Library per comportamento utente.
- Evita snapshot non motivati.
- Mocka solo confini esterni (API/router/time).
