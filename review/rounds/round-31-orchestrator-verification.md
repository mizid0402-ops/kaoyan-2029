# Orchestrator verification of the adversarial round (round 31, verifier fix)

Purpose: the adversarial reviewer (claude-sonnet-5) claimed FALSIFIED with 5 BLOCKERs against
Codex's fix of `tools/verify_tree.py`. A reviewer's claim is a proposal, not a fact, so each
central claim is reproduced here from the files. Round numbers refer to the reviewer's probe ids.

All mutations were made on temp copies under `%TEMP%\kaoyan-probe\verify\bypass\`. The five
protected files (4 trees + the tool) were hashed before and after and are unchanged.

## What I reproduced

| Probe | Claim | My result | Status |
|---|---|---|---|
| P1 | delete ALL 24 `scope=chapter` nodes from cs408 tree -> still passes | exit=0, `ALL CHECKS PASSED`, shape downgrades to `structure`, 0 failures | **CONFIRMED** |
| P3 | relabel chapters to `scope=section`, ids untouched -> still passes | exit=0, `ALL CHECKS PASSED`, shape `structure` | **CONFIRMED** |
| P16 | a lone orphan `item` passes because the structure-shape parent check never fires | exit=2, `ALL CHECKS PASSED` = False, so the check DID fire | **REFUTED** |
| control | removing one chapter must still go red | exit=1, 2 failures on the direct chapter-NN ancestor rule | correct |

## The real defect

Tree shape is inferred **solely from whether any node carries `scope == "chapter"`**. Therefore
the check that is supposed to protect the tree can be switched off by the very damage it exists
to catch:

- delete the chapter nodes -> no node has `scope=chapter` -> shape becomes `structure` ->
  the chapter/section checks do not run -> `ALL CHECKS PASSED`
- relabel the chapter nodes -> identical outcome, and it is cheaper to do by accident

So the round-31 fix is genuine for the four real trees (all pass, and a single removed chapter
still goes red) but its central promise — that an unrecognised or damaged shape is rejected
rather than reinterpreted — does not hold. **Silent shape downgrade is the blocker.**

## Correction to the reviewer

The reviewer's P16 probe is wrong: its structure-shape parent check does fire. Two of its
probes (P7/P8) it had already self-marked as defective. This is the fourth time in this project
that a probe of mine or a reviewer's produced a wrong number, so the count of confirmed
BLOCKERs is smaller than reported.

## What a fix would have to do

Infer the tree shape from the **id grammar**, not from a mutable `scope` label, and **fail**
when chapter-style ids (`<subject>.<domain>.chapter-NN`) exist while no node declares
`scope=chapter` — that is exactly the silent-downgrade signature. Restructuring trees is a
later, separate question.
