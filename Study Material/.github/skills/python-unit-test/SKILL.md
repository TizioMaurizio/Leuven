---
name: python-unit-test
description: Workflow multi-step per creare unit test Python (pytest/unittest) aderendo al setup del repository.
argument-hint: "Es: 'Aggiungi unit test per modulo X' o 'Copertura test per feature Y'"
compatibility: Python projects with existing test framework (pytest, unittest) or no tests.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: Python
  type: unit testing
  frameworks: [pytest, unittest]
  languages: [Python]
---

## User Input

```text
$ARGUMENTS
```

## Goal

Creare unit test Python focalizzati su logica, edge case e regressioni.

## Bundled assets

- `templates/test_module_template.py`

## Workflow

1. Rileva framework attivo (`pytest` o `unittest`) e convenzioni cartelle.
2. Mappa funzioni/classi critiche e path di errore.
3. Crea test parametrizzati e mock per dipendenze esterne.
4. Esegui test target e verifica failure output.
5. Riporta copertura incrementale e casi non coperti.

## Regole

- Se `pytest` è presente, preferiscilo.
- Non dipendere da rete/file system reale salvo fixture dedicate.
- Nomi test descrittivi e singola responsabilità per test.
