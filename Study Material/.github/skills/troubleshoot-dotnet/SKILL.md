---
name: troubleshoot-dotnet
description: Workflow per diagnosticare bug .NET/C# (NullReference, DI, async, config) e applicare fix minimali validati.
---

# Troubleshooter .NET

Usa questa skill per errori in applicazioni .NET/C#: eccezioni runtime, problemi DI/configurazione, async/await, regressioni in test.

## Obiettivo

- Riprodurre il problema con stack trace e contesto.
- Identificare componente e contratto violato.
- Risolvere con fix minimo mantenendo comportamento atteso.

## Workflow

1. Riproduzione
   - Esegui test/progetto che fallisce.
   - Raccogli stack trace completo, input e ambiente.

2. Diagnosi guidata
   - `NullReferenceException` -> catena null e inizializzazione dipendenze.
   - Errori DI -> registrazioni mancanti/lifetime incoerente.
   - Errori async -> deadlock, await mancanti, cancellation token ignorato.
   - Errori config -> binding opzioni, chiavi mancanti, ambiente.

3. Isolamento root cause
   - Riduci al test/entrypoint minimo che fallisce.
   - Conferma ipotesi con una modifica o check mirato.

4. Fix minimale
   - Correggi il punto causale (registrazione DI, null guard, mapping config, flow async).
   - Evita refactor non richiesti.

5. Validazione
   - Esegui test mirati prima, poi eventuale subset più ampio.

6. Report finale
   - Root cause, fix applicato, prove di validazione, rischio residuo.

## Check rapidi

- Lifetime DI coerente (`Singleton`/`Scoped`/`Transient`)?
- Nullability rispettata?
- Token di cancellazione propagato dove serve?
- Config strongly-typed valida all’avvio?

## Riferimenti

- Workflow ispirato ai pattern troubleshooting presenti in `github/awesome-copilot` (debug mode + approccio evidence-driven).
