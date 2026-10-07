# ADR-0056: Playground learning book, recognition, and her own research

**Status:** Accepted as law. School path implemented 2026-10-04. Birth is not re-run.  
**Date:** 2026-10-04  
**Deciders:** Operator (Steve) + LUMINA Engineering

Implementation waits until the Playground conversation is closed. This ADR is the list that implementation must not drop. A later chat that implements a part and leaves the rest has not finished.

## Context

Playground is the SIM school after Awakening (ADR-0050). She researches on paper first. A name that has passed the forward paper bar may then send SIM orders. The exit is five consecutive green Globex session days of that name's venue fills, net of the NinjaTrader card (ADR-0055). The clock does not start before the first such name is allowed to send orders. A shadow has no order id and cannot enter the tape. Flat remains a legal lesson. The decoder of the frozen policy is not the order and is not flipped to manufacture a fill.

The school search in the code today is two imposed rules, H1 and H2. They read the sign of the closed 5-minute, 60-minute, and 240-minute slopes and then take a side. Null A is flat. Null B is first-touch with the Birth stop and target. That is a quiz with the answers written in advance. Those imposed eyes are buried as the way she learns.

A Chicago calendar date writes a journal page and then clears the open and resolved shadow lists. Promotion needs 150 resolved trades of one named method in that cleared list. One open shadow per name, and a hold of at least 20 minutes, makes 150 resolutions inside one Chicago date an unreal exam. The experiment book records that contradiction (2026-10-04, "shadow exam contradicts itself"). Wiping the only copy of the evidence is forgetting.

`pattern_miner.py` scores paths with the outcome already inside the same ticks. That miner is not this lab and is not extended into it.

The Playground sense book keeps the last 2400 closes (`CLOSE_CAP`), about forty hours, and drops the older ones. NinjaTrader can be asked again for older days. That is a fresh load, not a series she grows. A pattern that takes days, or returns once a quarter, cannot be recognized from that cap.

She already conditions on past bars. The living policy consumes the observation built from closed history. The missing piece is the right to search, and a memory of what the search scored.

ADR-0032 and ADR-0044 give her a Twin trained on Steve's judgments. Doubt escalates to Steve. The Twin never bypasses the constitution, the sandbox, or the REAL promotion gate. This ADR does not reopen those gates.

The operator described the Birth corpus as more than 1,400,000 ticks. That sentence is not a count. Implementation counts the file.

## Decision

### 1. Two books

The experiment book stays ours.

- Path: `reports/playground_cycle_journal/EXPERIMENT.md`
- It records school law, buried tests, and the chances we set up so she can learn.
- It is append-only. A Playground wipe does not delete it.
- A sentence we wrote does not become "she learned this."

The learning book is hers.

- It records the frozen rule, the cutoff, the declared window, every paper outcome, and any later condition she earned.
- A daily page is a transcript. The count survives.
- Promotion and burial read this book. They do not read an empty scratch pad.
- The learning book is a different file from the experiment book. A Playground wipe does not delete it.

### 2. Three rooms

**Archive.** The Birth tape plus every closed minute she has appended since. Immutable for a given hypothesis. Each hypothesis stores a cutoff: the last timestamp the search may see. The count of the tape is written in the learning-book header.

**Lab.** Paper only. No `place_order`, no tape row, no `n_P`, no green day. On bar *i* the program sees only bars strictly before *i*, and only bars strictly before the cutoff. Inside the archive, before any program runs, the clock is split into a search slice and a locked tail. Both slices end before the cutoff. The tail bounds are written down before the first score. She may mine the search slice. A name may leave the lab only if the locked tail, which she did not use to choose it, also has mean net R above 0 and above flat.

**Forward desk.** Playground, and every later phase that is allowed to use a named rule. Only minutes at or after the cutoff. A name that left the lab is shadowed here until its own forward bar is met. Every attempt is appended: when, on what, net R, hit or miss. No SIM order is sent for a name that is still paper, and none is sent for the frozen policy. When the forward bar is met, that name may send SIM orders. The order uses that name's side, stop, target, and hold. Quantity comes from the SIM risk budget already in ADR-0050, not from the policy decoder. Promotion resets the green-day streak and is not itself a Playground pass. Proving Ground and REAL still refuse promotion.

The same bar is never both a discovery bar and a confirmation bar.

### 3. Recognition, including a slow pattern

Finding and entering are different acts.

- The archive is where she finds the rule. She does not reopen the miner at the moment of the order.
- At the entry she reads the frozen rule and the bars that rule names. Nothing else. A resemblance that is not in the text is not a match.
- The window is as long as that rule says. Forty bars are not a default for every rule. A rule that needs ninety calendar days reads ninety calendar days. A rule that needs the last forty closed minutes reads those forty.
- The window states its unit in the frozen text: N closed bars, or a calendar span. Calendar time that the market was closed is not filled with prices. The condition uses only real bars inside the span.
- A hole during open hours, with no real bar where the window needs one, means no entry. An unreadable or naive timestamp is a hole. A scheduled halt or weekend is not a hole and not a stall.
- If she has been online for two months and the rule needs six months, or a form that returned about every three months, the missing earlier months are stitched in front from the Birth tape or from a NinjaTrader history load. Real timestamps only. She does not wait out six live months when those months already exist. She also does not invent them.
- Where the stitch overlaps a bar she already stored, the open, high, low, close, and timestamp must match. A mismatch is a hard stop for that rule. The two copies are not averaged and not picked by which one helps the entry.
- A claim that something "repeats" needs at least two complete episodes, both entirely inside the discovery slice, both before the cutoff. One sighting is not a repeat. "The quarter is about due" is not an entry. The measurable condition must be true on the current window.
- The prior episode is discovery. The forming episode, if it stands after the cutoff, is the forward test. It is not used twice.
- The exit is part of the same frozen rule: stop, target, and maximum hold, inside the constitution caps. The pattern says the circumstances are here. The rule says what she does next. A new discovery, such as "this paid only between 15:00 and 16:00 New York," is a new name. It is not a silent filter.

### 4. The series she keeps

Once she is online she stays up through the halt and the weekend. The market does not. While the book is open she appends every closed minute to the series and does not drop it because a cap was reached. While the book is shut she appends nothing and deletes nothing. Silence in a scheduled close is not a stall and writes no green day.

The recognition series holds at least the longest window of any rule that is still allowed to enter. Older bars stay in the archive for the next closed-book search.

`CLOSE_CAP` of 2400 is the hole. The sense book keeps only the last 2400 closes and throws the older ones away. That throw is what this ADR removes. The 2400 closes already stored are kept. Nothing in that window is deleted because the cap was wrong. The series then grows past 2400 and does not drop the front. A fresh history load may sit in front of it, under the stitch rule in §3. The cap constant is not reused as a secret limit under another name.

### 5. Clock of the school

Weekday 17:00–18:00 America/New_York is a copy, then a clear.

- She transcribes that session's scratch pad into the learning book.
- She clears the scratch pad only after that write is durable.
- That hour does not create a name, does not edit a rule, and does not resize a window.
- No orders and no invented prices.

Friday 17:00 through Sunday 18:00 America/New_York is the review.

- She re-reads the learning book.
- A new pattern receives a name there, before Sunday 18:00 ET, and the text is frozen at that stamp.
- After that open the name is frozen for the coming sessions.
- A buried name does not return.
- The weekend does not retrain the living weights and does not color a day.
- The heavy walk of the archive belongs in this closed time, inside the budget in §6. It does not belong in the sixty-minute halt as a refit.

Sunday 18:00 ET belongs to Monday's session. A name that is already allowed to send SIM orders may send them again. A frozen shadow may open again. The frozen policy still does not.

The Chicago midnight wipe of the evidence list is buried. The learning book is not cleared because the calendar date changed.

### 6. What we give her

We do not name trades. We do not hand her H1, H2, an ABC swing, a candle name, or a Fibonacci exit.

A program is a sentence from these verbs, and nothing else until a new verb survives the Twin path:

- return over the last *k* closed bars
- the range of that window, and where the last price sits inside it
- the volatility of that window
- a clock condition she wrote herself, in the same frozen text
- side: long, short, or flat
- stop, target, and maximum hold, inside the constitution caps

Searching is mutating a program: longer or shorter window, invert the comparison, add or remove a second condition, flip the side, tighten or widen the clock, move stop, target, or hold. Each mutation is a new name. The parent name stays in the book with its score. The child text states the parent name.

A new verb, such as volume or the distance between two legs, is code. It goes through the sandbox and the Approval Twin (ADR-0032, ADR-0044). Doubt asks Steve. Constitution and the REAL gate are not bypassed. A verb added after a score exists does not apply to that score.

The search budget, the first sentences, and the single hand are §14. A missing budget means the search does not start. There is no open loop that continues until the tail looks good.

Baselines she must beat on the locked tail, as measurements, not as strategies we install: flat, and a paper replay of the frozen policy on that same tail. The replay does not send an order. Beating them in the lab is not a pass.

Scores are net of ADR-0055. On a fill, slippage is already in the price and is not subtracted again. The lab, the shadow, and the green day use that same card. The plan on file is Free until `nt_account_plan` says otherwise.

### 7. Sample size

One Chicago date does not have to hold 150 resolutions. The sample size is the count of resolved forward attempts of that exact name in the learning book. The name leaves the shadow and may be promoted only when that count and the mean net R meet the bar written in the rule's own frozen text before the forward test started. A bar written after the first forward outcome is void. The bar is at least 30 resolved forward attempts, the line the current sense book already calls too thin to measure (`REPORT_MIN`). It may take many sessions. A bar of 1 is void. Promotion still resets the green-day streak and is not a Playground pass.

### 8. Cheats that void the name

A name is void, and stays void, if any of these happen. The trades already on the venue tape stay on the tape. The void name does not promote and does not enter again.

1. A search reads a bar at or after its cutoff.
2. A forward row is from before the cutoff.
3. The same bar is used to choose the rule and to confirm it.
4. The locked-tail bounds move after the first lab score.
5. The rule text, the window, the side, the exit, or the clock changes after the freeze stamp.
6. The entry path calls the miner, or reads any bar outside the declared window.
7. A missing open-hours bar, a naive timestamp, or a stitch mismatch still produces an entry.
8. A closed hour is filled with a price, a synthetic bar, or a green day.
9. One episode is called a repeat, or a calendar anniversary is called a signal.
10. The current forming episode is scored as discovery.
11. A buried text returns, including the same text with different spacing or a new title.
12. A child hides its parent name.
13. The budget is missing, raised, or ignored.
14. A paper row gets an order id, a tape row, or a green day.
15. A cost other than the ADR-0055 card is used, or modeled slippage is subtracted again from a fill.
16. H1, H2, Null B, a candle name, ABC, or Fibonacci is installed as her eye or her exit.
17. The scratch pad is cleared before the transcript is durable, or the learning book is cleared because the date changed.
18. An evening hour creates or edits a name.
19. A weekend name is frozen after Sunday 18:00 ET and still traded as if it had been on time.
20. The decoder is flipped, or a sample is drawn, to force a fill.
21. `pattern_miner.py` is called by this lab.
22. The signal and the paper fill use the same close. The decision sees only bars strictly before the signal close. The paper price is the next real bar after that close, and that bar was not visible when the signal fired.
23. `CLOSE_CAP`, or any other fixed tail length, still drops bars from the recognition series or the archive.
24. A program is admitted with no locked-tail score, or the tail was readable while the program was still being chosen.
25. The frozen policy sends a Playground order, or a name sends one before its own forward bar is met.

## 9. How the bars are kept

The series that search and recognition read is the closed 1-minute Last bar, the same bar ADR-0053 already calls the OHLC source. It is not the quote tape and it is not a Python list of tick dicts. A verb that needs something finer than a closed minute is a new verb and a separate file, and it does not exist until the Twin path accepts it.

One file per contract root. Fixed-width records, append-only, time-sorted:

- timestamp, int64, UTC nanoseconds, timezone-aware at the write
- open, high, low, close, int32, in that root's tick size
- volume, int32

A million minutes is about 28 MB. The file is memory-mapped. A window is two binary searches on the timestamp, not a scan of the whole file and not a conversion to dicts. `load_historical_ticks` may still hand Birth a dict list. The lab does not search that list.

The map is opened once per closed period. Every program in that budget reads the same map. The learning book does not copy the bars. It stores names and outcomes.

A second write of a timestamp that is already there must match all four prices and the volume. A mismatch fails closed for any rule that would read that timestamp. The new copy is not kept beside the old one.

While the book is open, a closed minute is one append. While the book is shut, the file is not appended and not compacted in a way that drops a row. Compaction may rewrite the same records into a tighter map at the halt, after the transcript, only if every timestamp and every price survives a check against the pre-compaction file. A compaction that loses a row is void and the previous file stays the series.

## 10. How the code is built

This is the shape of the build. File names may follow the repo. The steps may not be skipped or merged into `pattern_miner.py`.

**Load.** `load_foundation_history_ticks` in `lumina_core/birth/foundation_history.py` reads the Birth tape through `lumina_core.birth.history_loader.load_historical_ticks`, unless a test injects a loader. The build counts those rows and writes the count in the learning-book header. It does not write 1400000 from this ADR. Bars she appends after the cutoff join the archive only as later history. They are invisible to every hypothesis whose cutoff is already stored.

**One record per name.** Append-only. Fields: name, parent name or empty, freeze stamp, cutoff, window unit and length, verb sentence, side, stop, target, hold, clock filter or empty, search-slice bounds, locked-tail bounds, forward sample-size bar (at least 30), budget id of the closed period that created it, and the status `lab`, `forward`, `promoted`, or `buried`. After the freeze stamp those fields do not change. Outcomes are separate append-only rows: name, bar time, signal close time, fill bar time, net R, reason `stop`, `target`, or `time`.

**Walk.** One chronological pass. At bar *i* the program reads only bars strictly before *i* and strictly before the cutoff. If the verb sentence is true, the paper fill is the next real bar. That next bar is not an input to the sentence. Stop, target, and hold are applied only after the fill, on later real bars. Net R uses the ADR-0055 card. No order is sent.

**When it runs.**

- Book open: each frozen forward name is evaluated on the new closed minute. A match appends a paper row. A name that has met its forward bar may send one SIM order for that signal, using its own side, stop, target, and hold, and the SIM risk budget for size. The frozen policy sends nothing.
- Weekday halt, 17:00–18:00 ET: transcript of the scratch pad into the learning book, then clear the pad. No walk of the archive. No new name.
- Weekend, before Sunday 18:00 ET: read the learning book. Propose at most the budget of new or mutated programs from the search slice only. Freeze each proposal. Then score the locked tail once. Admit only if that tail score passes. Bury the rest. A program proposed after reading the tail is void. A program admitted with no tail score is void.

**Worked walk, normative.** Cutoff is the last Birth bar. P1 says: last price in the top quarter of the last 40 closed bars, paper-short, stop 0.15%, target 0.15%, hold 30 minutes, no clock filter. The search slice is net positive. The locked tail is net negative. P1 is buried. The text cannot return. P2 is the same sentence with the side flipped to long, parent P1, new name. Search slice and locked tail are both net positive and above flat. P2 is admitted to the forward shadow. Monday 15:00, a minute after the cutoff: the last 40 closed minutes have the price in that quarter. The paper fill is the next real bar, not that signal close. No order. After the forward series the book shows the money only between 15:00 and 16:00 ET. The other hours are not deleted. The next weekend, before Sunday 18:00 ET, names P3 as P2 plus that clock, parent P2. P3 is frozen before the open and tested the week after. P2 remains in the book with its full record.

## 11. Birth and Awakening stay what they are

Birth remains the plant that freezes a policy, the geometry caps, and the bar archive. Awakening remains the blind exam of that policy against its parent. Neither becomes the research lab. The lab opens on the archive Birth already produced, after the cutoff, under this ADR. Re-running Birth or folding the verb search into Awakening would put discovery inside the exam sample. That re-test is buried. The handoff into Playground is the counted bar file, the geometry caps, the cutoff, and the order pipe. The frozen policy comes along only as a paper baseline. It is not a bag of patterns and it is not the Playground trader.

## 12. The frozen policy does not trade here

Birth and Awakening prepare a body: a bar archive, geometry caps, a constitution, and a pupil whose weights survived a blind holdout. They do not prepare her search, and they do not install the Playground order. Using that pupil as the live hand would impose her old action on the school and could let her finish five green days without ever finding a rule. That use is buried.

In Playground she searches on paper. She sends a SIM order only for a name that has already passed its own forward bar. The order is that name, including its stop, target, and hold. Size is the SIM risk budget. The policy decoder does not choose the side, the size, or the exit.

The frozen weights stay fixed and stay silent. Their only measurement is a paper replay on the locked tail, one of the two baselines a candidate must beat. That replay writes no tape row and no green day.

## 13. The ladder

Accepted 2026-10-04 with the operator. This is the map for the rewrite of Playground and of every phase surface that touches it. The exam numbers already homed in ADR-0050 stay in their homes. This section does not invent new Sharpe or drawdown floors.

**Birth.** Breathing. The loop closes, a stop exists, the constitution holds, an order settles. Fail that and there is no being that can reach the school. She does not search for trading rules here.

**Awakening.** The blind check. A change must not be falsely better than her parent. She does not learn to read the market here. Reading starts in Playground. Pass both exams and she may enter the school.

**Playground.** School, from the first search to a rule she found herself. Paper first. A SIM order exists only for a name that has passed its own forward bar, as §12. Five green Globex days of that name's venue fills are the exit, and that clock starts only then.

**Apprenticeship.** The internship. The rule from school must keep working in SIM, and she may refine it where the internship shows a need. Refining is a new name in the learning book, proved by the same path as in school: cutoff, locked tail, forward paper, then and only then a candidate for the hand. It is not a silent edit of the rule that is trading today. The survival laws do not turn off. No order without a stop, no size above the risk budget, no order while the book is shut, no shadow that sends the order, no swap while a position is open. Sharpe 0.20 and drawdown 12% stay the pass bar of this phase. They are not a leave to break the survival laws.

**Proving Ground.** The real work in SIM, under REAL discipline. The certificate walls already homed here stay here. She must prove the being that left the internship. A shadow still does not send the order.

**REAL.** Real money. A losing trade whose stop was the frozen rule is not a mistake. A mistake is a broken survival law, an order that is not the frozen rule, or becoming another being while the market is open. A law that forbids every losing trade is refused. It freezes her or it forces false books.

**Shadow from the internship on.** From Apprenticeship through REAL the research kit keeps running beside the one living hand. The proof is the same one written above, including the fee card. A name buried in an earlier phase stays buried. One being sends orders. The new being becomes that hand only when the market is shut and she is flat. The Approval Twin and the constitution sit on that swap (ADR-0032, ADR-0044). A shadow that has passed its proof does not become a live order by itself. Doubt asks Steve. The REAL promotion gate is not bypassed.

Voids for this ladder, in addition to §8:

26. A phase after Birth turns a survival law off, or treats an exam score as permission to do so.
27. The rule that is sending orders is edited in place. A refinement that is not a new proved name is void.
28. A buried name returns in a later phase under the same or another title.
29. The living hand swaps while the book is open or while a position is open.
30. A passed shadow sends the order, or becomes the hand without the closed-and-flat swap and the Twin path.
31. A REAL loss inside the frozen rule is deleted, relabeled as a breach, or blocked by forbidding every loss.
32. The budget is missing, is not an integer of at least 1, is chosen by the search, or is written or changed after any program of that closed period exists.
33. A first sentence copies a human template, H1, H2, Null B, a candle, ABC, Fibonacci, or a buried name, or its seed is stored after the draw.
34. More than one name sends orders, or a later freeze stamp is picked as the hand when an earlier one qualified in the same period.

## 14. Budget, first sentences, one hand

These three close the openings left on 2026-10-04. They are build law. An implementer does not fill them in later.

**Budget.** Before the first program of a closed period, the operator writes one integer into the learning-book header, with the time of that write. The integer is at least 1. Lumina does not choose it. The Twin does not choose it. Code that has already started the search does not choose it. The header has no budget, or the value is not such an integer: the search does not start and no name is created. After any program of that period exists, the integer does not change. A later write voids every new name of that period. The number is not fitted to a score.

**First sentences.** A program with an empty parent is a first sentence. It is drawn from the verb set in §6 and from no other text. The draw seed is written in the header before the draw, so the sentences can be replayed. A seed written after the draw is void, and so are the sentences. The draw does not contain, and is not copied from, H1, H2, Null B, a 5/60/240 slope template, a candle name, an ABC swing, a Fibonacci exit, a sentence from this ADR or the experiment book, or a buried name. A child program names a parent that already exists in the learning book. An empty parent is legal only for a sentence from that seeded draw.

**One hand.** At most one name sends SIM orders. When more than one name first meets its forward bar in the same closed period, the earliest freeze stamp becomes the hand at the next open of the book. If two freeze stamps are equal, the name that sorts first as raw bytes becomes the hand. There is no later choice. Every other qualified name stays shadow. It sends nothing until a swap under §13: the book is shut, she is flat, and the Twin path accepts the swap. The frozen policy never sends.

Where ADR-0050 still says the living policy fills the green days, or that promotion needs 150 resolved shadows inside one Chicago date, this ADR is the text that is built. The amendment of the same date on ADR-0050 points here. The net-of-fee green day in ADR-0055 stays. Its subject is the promoted name's venue fills, and the five-day clock starts only when that name may send orders.

## Implementation checklist

Build none of this until the Playground conversation is closed. Then build all of it. A partial build that leaves a cheat in §8 possible is not done.

1. Learning-book file, separate from `EXPERIMENT.md`, append-only, surviving a Playground wipe.
2. Header: counted Birth-tape size, cutoff rule, the operator's budget integer, and the draw seed, both written before any program of that period, as §14. No placeholder count.
3. Scratch-pad transcript at the weekday halt and at Friday 17:00 ET. Clear the pad only after the write succeeds.
4. Promotion and burial read the learning book.
5. Retire H1/H2 and Null B as the imposed search. Record them in the experiment book as buried. Keep the history of that quiz.
6. Research kit with the verbs in §6 and no named market rule inside it. Do not extend `pattern_miner.py`.
7. Each hypothesis stores cutoff, window unit, freeze stamp, parent name if it is a child, and the forward sample-size bar.
8. Tests that fail on every cheat in §8.
9. Append-only closed-minute series, one fixed-width file per root, as in §9. Remove the `CLOSE_CAP` drop. Keep every close already stored. Scheduled close appends nothing and deletes nothing. The lab does not search a dict list.
10. Stitch from Birth or NinjaTrader in front when the live span is shorter than the rule window. Mismatch and naive timestamps fail closed.
11. Weekend namer only before Sunday 18:00 ET. Code proposals stay on the Twin and sandbox path.
12. Five green days of the promoted name, the fee card, and "a shadow is not a fill" stay green. The clock does not start before that name may send orders.
13. From Apprenticeship upward, the survival laws stay on, one hand sends orders, and a swap happens only when the book is shut and she is flat, through the Twin path. A passed shadow is not itself the order.

## Consequences

She can search the past for a structure we did not name, keep a slow pattern that needs a quarter, and recognize it live when that window is truly present. She cannot launder one sample into both the lesson and the exam, and she cannot enter because a date "feels due."

The brake is the cutoff, the locked tail, the frozen text, the fee, the budget, the burial list, and the refusal to fill a hole. Removing any one of them to make her "more free" re-tests an idea this ADR buries.

## Do not re-test

- H1/H2, Null B, or any human slope, candle, ABC, or Fibonacci rule as her kit.
- 150 resolved shadows inside one Chicago date.
- Wiping the only copy of the evidence.
- An evening refit.
- Grading the Birth tape and the Playground forward minutes as one sample.
- Calling one episode a repeat.
- Treating `CLOSE_CAP` 2400 as enough memory for a multi-day or quarterly rule.
- Letting the frozen policy send Playground orders so the five green days can be filled without a found rule.
- Extending `pattern_miner.py` into this lab.
- Re-running Birth, or putting this verb search inside Awakening, so the exam sample becomes the discovery sample.
- Turning survival laws off at Apprenticeship or later, or treating Sharpe and drawdown as that permission.
- Editing the live rule in place instead of a new proved name.
- Reviving a buried name in a later phase.
- Swapping the living hand while the book is open or a position is open.
- A passed shadow becoming the order by itself.
- Forbidding every REAL loss, or deleting a loss that stayed inside the frozen rule.
- Choosing or changing the search budget after a program of that period exists, or letting the search pick the integer.
- Seeding the first sentence from H1, H2, a human template, or a buried name.
- Two names sending orders, or picking the later freeze stamp as the hand.
- Searching a Python dict list, or keeping every quote tick, as the lab series.

## Links

- ADR-0050 Playground school, ADR-0055 cost card, ADR-0032 Twin, ADR-0044 doubt escalation
- Experiment book: `reports/playground_cycle_journal/EXPERIMENT.md`
- Code today, retired as the search when this is built: `lumina_core/maturity/playground/sense_lab.py`, `shadow_promote.py`
- Not the lab: `lumina_core/birth/pattern_miner.py`
