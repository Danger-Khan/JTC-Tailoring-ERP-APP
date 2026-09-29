# scheduler-java — can the shop keep its promises?

Given orders with delivery dates and estimated hours, and tailors with daily
capacity and skills: who cuts what, and **which delivery dates are not
physically reachable**.

## The gap it fills

The desktop app lets you type a delivery date and pick a tailor from a
dropdown. Nothing anywhere checks that the two are compatible. Promise six
suits for Friday to one man who works seven hours a day and the app records it
without a murmur — and nobody finds out until Friday.

```
$ java -cp out jtq.Main --in sample-workshop.json

SUMMARY : 9 scheduled, 2 will miss their date, 1 cannot be placed

TAILOR LOAD
  Usman Ali     8.0 h/day  booked  21.0 of  88.0 h    23.9%  ORD-103,ORD-108,ORD-105
  Imran Khan    7.0 h/day  booked  18.0 of  77.0 h    23.4%  ORD-101,ORD-107
  Bilal Ahmed   6.0 h/day  booked  61.0 of  66.0 h    92.4%  ORD-102,ORD-109,ORD-104,ORD-106

PROBLEMS
  [late] ORD-104 (Ayesha Khan): not enough capacity before the promised date
        promised 2026-02-09, earliest possible 2026-02-10 -> 1 days late
  [late] ORD-106 (Zain Abbas): not enough capacity before the promised date
        promised 2026-02-10, earliest possible 2026-02-13 -> 3 days late
  [unassignable] ORD-110 (Adeel Butt): no tailor on duty has the skill: embroidery
```

The interesting line is not either late order. It is **92.4% against 23.9%** —
Bilal Ahmed is the only tailor who can do sherwani or coat work, so every such
order queues behind him while two other tailors sit near-idle. Both late orders
are his. That is a hiring or cross-training decision, and it is invisible in a
list of orders.

## Why Java

`java.time`. This problem is dates, calendars, working days and durations, and
`LocalDate`/`DayOfWeek`/`ChronoUnit` are better at it than anything in the
other two languages' standard libraries. No timezone traps, no
seconds-since-epoch arithmetic, no dependency.

Records also make the domain nearly declarative — `Tailor`, `Order`,
`Assignment`, `Shop` are one line each — and Java 25's pattern-matching
`switch` made the JSON reader pleasant to write rather than a chore.

## The algorithm

Earliest due date first. On a single machine EDD is optimal for minimising
maximum lateness: if *any* ordering can meet every deadline, sorting by
deadline meets every deadline too. With several tailors that guarantee no
longer holds, so this is a heuristic — and therefore it always reports the gap
it could not close rather than picking a winner and going quiet.

Each order goes to whichever qualified tailor would **finish it soonest**, with
ties broken toward whoever is carrying less work. Capacity is tracked per
tailor per day, so closed days and differing hours-per-day fall out naturally.

## Input

```json
{
  "start": "2026-02-02",
  "workingDays": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
  "tailors": [
    { "id": "E-1", "name": "Usman Ali", "hoursPerDay": 8, "skills": ["kameez", "shalwar"] }
  ],
  "orders": [
    { "id": "ORD-101", "customer": "Farman Saim", "garment": "Shalwar Kameez",
      "hours": 9, "due": "2026-02-05", "skill": "kameez", "priority": 0 }
  ]
}
```

A tailor with no `skills` is treated as a generalist. An order with no `skill`
can go to anyone. `priority` breaks ties between orders due the same day.

JSON in and JSON out, on purpose: nothing here opens an `.xlsx`, so it can be
pointed at a copy of real data with no chance of writing into the shop's books.

## Usage

```sh
javac -d out -Xlint:all src/jtq/*.java
java -cp out jtq.Main --in sample-workshop.json [--out plan.json] [--start 2026-02-02]
java -cp out jtq.Main --selftest
```

Exit code 3 when something is late or unplaceable, so it can sit in a nightly
check and raise its hand.

## Tests

26 checks, `--selftest`, no JUnit — the point was a single `javac` and no
downloads. They cover the JSON reader (including five malformed inputs that
must be rejected rather than half-parsed), capacity arithmetic, closed days,
EDD ordering, skill matching, lateness, load spreading, and the two ways this
could hang forever: a tailor with zero hours, and a shop that is never open.

## If this were ever wired in

It is not. The honest blocker is that **the app does not record how long a
garment takes**. Every `hours` figure in `sample-workshop.json` is invented.
Without that number this is a well-tested engine for data nobody is collecting,
so the first real step is not code — it is deciding whether the shop will
record an estimate per garment type, which is a question for the owner.

A cheap start would be a fixed table per garment type (a kameez is ~9 hours, a
sherwani ~22), refined later from actual delivery dates. The engine does not
care where the number comes from.
