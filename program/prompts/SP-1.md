# SP-1 — small points: `paused` note in the layout header; "31 of 31" note on the concept page

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers edit other files now; touch only the allowed ones.
- `modules/interfaces/cpp/livemeas/livemeas_layout.hpp` (struct `MeasStatus`, member `status`)
- The concept page `/mnt/c/ws/lt_learning/sim/vantage_concept.html` (outside every repo),
  line 498, the sentence "Our model showed it: 31 of 31 matches failed when one producer
  renumbered."

## Goal
Owner decision 6 (2026-10-30): `paused` is kept with a note that nothing writes it yet; the
concept page's "31 of 31" stays, with a note that it was measured before D16-D18.

## Allowed changes
- `modules/interfaces/cpp/livemeas/livemeas_layout.hpp`, the trailing comment of `status` only
- `/mnt/c/ws/lt_learning/sim/vantage_concept.html`, that one sentence only
- Everything else is read-only.

## Steps
1. Copy the concept page to
   `/mnt/c/ws/lt_learning/sim/backup/vantage_concept_before_SP-1.html` first (do not
   overwrite an existing file of that name; if one exists, stop and report).
2. In `livemeas_layout.hpp`, the comment of `status` becomes
   `///< 0 starting, 1 running, 2 paused (nothing writes it until the developer face gets pause), 3 finished`.
   Keep the member's alignment as close as the line length allows; change nothing else.
3. In the concept page, right after "31 of 31 matches failed when one producer renumbered."
   add: ` (Measured with the model before decisions D16-D18; it will be re-run on the lab.)`
   Keep the surrounding markup intact.

## Exit check (run all, report output and seconds)
- `git -C modules/interfaces diff --stat` → that one file, 1 insertion, 1 deletion (plus any
  file another worker changes in `docs/resim_contract/`; list it, do not touch it).
- `grep -c "it will be re-run on the lab" /mnt/c/ws/lt_learning/sim/vantage_concept.html` → 1
- `python3 -c "import html.parser,sys; p=html.parser.HTMLParser(); p.feed(open('/mnt/c/ws/lt_learning/sim/vantage_concept.html',encoding='utf-8').read()); print('parsed')"` → `parsed`
- `ls -l /mnt/c/ws/lt_learning/sim/backup/vantage_concept_before_SP-1.html`

## Must not
- commit, push, or change files outside "Allowed changes"
- change any struct member, type or order

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
