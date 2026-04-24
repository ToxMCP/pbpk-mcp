# OSPSuite Population Feasibility Spike

This memo records the intended feasibility path for native OSPSuite population execution. It is a design/decision artifact only. No public API change is implied by this note.

## Candidate R API Path

Feasibility target:

- create or resolve a PK-Sim population in R
- execute the population run through the OSPSuite R surface
- normalize the result into the same high-level `resultsId` plus retained-chunk model used today for `rxode2` population output

The current blocker is not the idea of population execution itself. The blocker is safe runtime packaging and result transport.

## Required Runtime Strategy

Any production implementation should default to:

- chunked persistence instead of a single in-memory JSON result
- explicit subject/time chunk metadata
- aggregate previews for mean/SD style reviewer-facing output
- hard caps on subject count, output count, and time-grid size

Large subject-by-time matrices should not be pushed through stdout as one payload.

## Result-Size And Memory Limits

Go/no-go constraints for a first implementation:

- refuse very large cohorts unless chunked persistence is enabled
- cap the number of selected outputs
- cap the time grid or derived row count
- keep at least one reviewer-facing aggregate path even when chunk payloads are retained off the main response

## Parity Expectations Versus `rxode2`

Reasonable parity targets:

- same high-level job lifecycle
- same `resultsId` concept
- same chunk-handle abstraction
- compatible aggregate keys where the underlying engine can supply them

Non-goals for the first cut:

- exact numeric parity with `rxode2`
- identical cohort-generation semantics
- a promise that every OSPSuite model will support the same population workflow

## Recommendation

Current recommendation: `go for a bounded engineering spike, not for immediate public exposure`.

That spike should prove:

- the R API path exists for the selected reference models
- chunking avoids stdout/memory blowups
- review/report surfaces can consume the resulting aggregates without special cases

If those checks fail, keep OSPSuite population support as a documented future capability rather than exposing a weak or unstable public tool.
