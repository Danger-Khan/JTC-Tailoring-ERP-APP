# cutlist-cpp — fabric cutting plan

Given bolts of cloth of a fixed length and a list of garment pieces, work out
which pieces come off which bolt.

## The part that is not textbook bin-packing

Minimising the number of bolts is the standard problem and the easy half.
The half that matters to a tailor is **where the leftover ends up**.

Total waste is nearly fixed once you know the bolt count — you cannot conjure
cloth. What you *can* change is whether that waste comes out as six half-metre
offcuts or one three-metre remnant. Six offcuts go in the bin. A three-metre
remnant is a child's kameez, a set of pockets, a lining.

So the objective is lexicographic:

1. fewest bolts opened, then
2. longest single remnant.

```
Bolts to open    : 2  (lower bound 2, optimal)
Total waste      : 11.60 m
Longest remnant  : 10.50 m  (keep this one)
Unusable offcuts : 0  (under 0.50 m)

Without gathering the remnant (--plain): 2 bolts, longest remnant 10.20 m
```

Same cloth, same waste, 30cm more of it in usable form.

## Why C++

It is a search over arrangements: pack, then try every single-piece move
between bolts, keep the ones that improve the score, repeat. That is a tight
loop over plain structs copied by value, and C++ gives you exactly that with
nothing in between — no allocator surprises, no GC pause, `std::vector<Bolt>`
laid out contiguously.

It is also the language where getting that wrong is easiest, which the
development of this file demonstrated (below).

## How it works

- **Lower bound** — `ceil(total length / bolt length)`. No plan can beat it, so
  the report can say *optimal* rather than merely *good*.
- **First-Fit-Decreasing** — longest piece first into the first bolt it fits.
  The classic result is that FFD never needs more than `11/9 · OPT + 6/9`
  bolts, and on realistic cut lists it hits the bound exactly.
- **Gather the remnant** — hill-climbing on the score above. Move one piece,
  keep the move only if the score actually improves.

### The bug worth recording

The first version of the gathering step moved each piece to wherever it fit
tightest and assumed that had to help. The comment above it even claimed it was
"strictly improving". It was not — there was no improvement test at all, and on
the sample cut list it turned a 10.2 m remnant into a 9.3 m one *while
reporting success*.

Every test still passed, because they all checked that the plan was **valid**:
every piece placed once, no bolt over length. A plan can be perfectly valid and
worse than the one you started with.

What caught it was printing the before-and-after and looking at the numbers.
What keeps it caught is a test that runs both paths over five cut lists and
asserts the tuned one is never behind plain FFD — plus one that asserts it is
sometimes ahead, so the whole step cannot be quietly reduced to a no-op.

Hill climbing without checking you went uphill is just walking.

## Usage

```sh
cutlist --in sample-cutlist.txt        # human readable plan
cutlist --in sample-cutlist.txt --json # machine readable
cutlist --in sample-cutlist.txt --plain # skip the gathering step, to compare
cutlist - < sample-cutlist.txt         # from stdin
cutlist --selftest
```

Input format, one directive or piece per line, `#` starts a comment:

```
bolt 50        # bolt length in meters
kerf 0.1       # allowance lost per cut: straightening + seam (optional)
ORD-101 6.5    # a piece: id, then meters
```

The `kerf` matters more than it looks. Three 3 m pieces fit a 10 m bolt; the
same three at 0.1 m allowance each do not. Forgetting it is how a shop ends up
one bolt short in the middle of a job.

Exit code 3 if any piece is longer than a whole bolt — those are reported, not
silently dropped.

## Build

```sh
g++ -std=c++20 -O2 -Wall -Wextra -o cutlist cutlist.cpp
```

Single file, no dependencies, no build system. Compiles clean under
`-Wall -Wextra`.

## If this were ever wired in

It is not. To be useful it would need a per-garment fabric requirement, which
the app does not currently record — `GarmentCalculator.estimate_fabric_meters()`
in `app/services/garment_engine.py` computes one from the measurements, and
feeding its output in here is the obvious join. That is a real feature with a
data-entry question behind it (does the shop track bolts at all?), which is why
this stops at a command line tool.
