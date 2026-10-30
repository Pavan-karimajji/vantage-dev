# <MODULE> — concept

<!--
TEMPLATE (R-REQ-17). A `concept` supporting document. Copy, rename to
<MODULE>_Concept.md, declare it under `context:` in layers.yaml, and cite it
from at least one requirement document or the checker reports it unreferenced.

THREE RULES, and the checker enforces two of them:

  1. NO UIDs ALLOCATED. Cite `SYS-0004` freely -- that is how this document
     connects to the set. Never write the requirement anatomy
     (**`SYS-0004`** · `P0` · `R1` — headline / **Shall.** ...). C-CONTEXT-UID.
  2. CITED BY THE SET. Some requirement document, the test spec or the plan
     names this file. C-CONTEXT-UNREF.
  3. NO EXECUTION NARRATION. Not checked, and it is the one that decays first.
     THE TEST IS TENSE: this document says what IS true of the problem. What
     happened during a session -- what was run, what was found, how long it
     took -- belongs in a Test Execution Record, a commit message, or git log.

There is NO length cap and NO commentary cap here (R-REQ-14). Commentary is the
entire point of this document. Write as much as the problem needs.

Delete this comment block.
-->

**A supporting document** (`R-REQ-17`, declared under `context:` in
`layers.yaml`). It carries the reasoning; the requirement documents carry the
obligations. Nothing here is a requirement, and nothing here allocates a UID.

## 0. What this is, in one paragraph

<!-- The problem in plain language, before any solution. A reader who knows
     nothing about this module should be able to stop after this section and
     say what it is for. -->

## 1. The problem

## 2. Why it is hard

<!-- The part that is not obvious. If nothing here is surprising, this document
     may not need to exist -- and that is a fine conclusion. -->

## 3. Prior art / what binds us

<!-- Standards, regulations, physics, an existing interface. Where a retrieved
     document backs a claim, cite it by clause and keep the file under the
     directory declared as `kind: reference`. -->

## 4. Derivation

<!-- The mathematics, if there is any. Give every quoted number a reproducible
     source: a script under py/ that prints it, cited by an identifier, so a
     reader can check any figure in one command rather than trusting it. -->

## 5. Frozen decisions

<!-- What must not be silently reopened, each with the reason and the evidence
     it rests on. This is the section future readers actually come back for. -->

| # | Decision | Because |
|---|---|---|
| **DD-1** |  |  |

## 6. What this concept deliberately does not settle

<!-- Open questions, each with an owner. A question named here is a question
     somebody can answer; a question left implicit gets answered silently at a
     keyboard by whoever hits it first. -->
