# Next plan — to be determined by Plan 007_3 findings

Status:
not_yet_drafted

The 007_3 verification ledger + adjudication determine the next plan:
- All verdicts PASS, theorem-family resolves, low dup-number risk → production
  hardening / corpus expansion (Plan 007_1).
- Corpus lacks theorem-bearing documents (likely) → Plan 007_1 to add a
  theorem-bearing fixture so 006_5 can be confirmed on real data.
- theorem duplicate-number count high → duplicate-number disambiguation fix.
- Post-refactoring calibration differs materially from the router's baseline →
  a plan to re-point the `--calibration-weights` default.
- Any FAIL → a targeted fix plan for that subsystem.
