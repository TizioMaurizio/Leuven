---
name: dotnet-unit-test
description: Workflow multi-step per creare unit test .NET rispettando framework e convenzioni esistenti (xUnit/NUnit/MSTest).
argument-hint: "Es: 'Aggiungi unit test per modulo X' o 'Copertura test per feature Y'"
compatibility: .NET projects with existing unit test framework (xUnit, NUnit, MSTest) or no tests.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: .NET
  type: unit testing
  frameworks: [xUnit, NUnit, MSTest]
  languages: [C#]
---

## User Input

```text
$ARGUMENTS
```

## Goal

Creare unit test .NET affidabili, con Arrange/Act/Assert chiaro e copertura dei casi principali.

## Bundled assets

- `templates/UnitTestTemplate.cs`

## Workflow

1. Rileva framework test corrente nel solution (`xunit`, `nunit`, `mstest`).
2. Identifica classi/metodi target e dipendenze da isolare.
3. Crea test usando il template e naming coerente.
4. Esegui test per progetto/file target (`dotnet test` mirato).
5. Riporta esito, copertura aggiunta e gap.

## Regole

- Non cambiare framework di test se ne esiste già uno.
- Favorisci test indipendenti e ripetibili.
- Mocka servizi esterni (DB, HTTP, clock, filesystem).
