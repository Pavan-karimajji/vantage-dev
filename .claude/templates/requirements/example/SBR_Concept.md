# SBR — concept

**A supporting document** (`R-REQ-17`, declared under `context:` in
`layers.yaml`). It carries the *thinking*, so the requirement documents can
carry only the result. It allocates **no UIDs** and states **no obligation** —
if a sentence here starts "shall", it is in the wrong file.

Exempt from `commentary_lines_per_requirement`, because commentary is the
entire point of it. What is capped here instead is **execution narration**:
a line about what someone ran, found or fixed during a session belongs in a
Test Execution Record or a commit message. **The test is tense** — a concept
document says what *is* true of the problem, never what *happened* last Tuesday.

## 1. The problem

An occupant who is not belted is far likelier to be injured in a crash. A
reminder is the cheapest available intervention: it costs nothing to build
into a car that already senses belts and seats, and it works by making the
unsafe state slightly annoying rather than by restraining anybody.

## 2. Why a reminder escalates

A single chime is easy to miss and easy to ignore, and an occupant who ignores
one has usually not decided anything — they were talking, or reaching for
something. Escalation converts an unnoticed reminder into a noticed one
without ever becoming an override: the driver may always choose not to belt.

That is the whole justification for `STK-0003` existing as a separate
stakeholder row rather than as a clause on `STK-0001`.

## 3. Why the false-reminder rate is a stakeholder concern

A reminder that fires for a belted occupant, or an empty seat holding a bag,
teaches the occupant that the system is wrong. Once taught, they ignore the
true reminders too — so a false reminder does not merely waste attention, it
**removes** the mechanism's only means of working. `STK-0004` therefore states
a rate, not a behaviour.

## 4. Why speed gates it

A stationary vehicle with a door open is loading, not driving. Gating on speed
is what separates *"the car is in use"* from *"somebody is sitting in it"*,
and it is the reason `egoDyn` is an input to a function that is otherwise
about belts and seats.

## 5. What this concept deliberately does not settle

- **The escalation schedule.** How many stages, and how far apart, is a
  calibration question with a customer's number behind it, marked `⊘`.
- **The modality.** Chime, telltale or both is an HMI decision.
- **Rear-seat scope.** Which seats are covered is a programme decision, and
  the set is written so that adding a seat adds calibration, never a row.
