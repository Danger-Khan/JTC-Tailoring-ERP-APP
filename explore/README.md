# explore/

Three prototypes in three languages, **deliberately not wired into the app**.

Nothing in here is imported by any Python module, nothing reads or writes
`app/data/`, and nothing runs when `Start.bat` runs. They are standalone
command line tools that take a file in and print a result out. If one of them
earns its place later, wiring it in is a separate decision — the point right
now is to see what each language is actually good for on this codebase's real
problems.

Each one was picked because the language suits it, not to tick a box:

| Tool | Language | Why this language |
|---|---|---|
| [`cutlist-cpp/`](cutlist-cpp/) | C++20 | A search over arrangements. Tight loops over plain structs, no runtime to fight. |
| [`barcode-rs/`](barcode-rs/) | Rust | A spec you must implement *exactly*. Exhaustive `match`, a real type for every error, and tests that check the table instead of trusting it. |
| [`scheduler-java/`](scheduler-java/) | Java 25 | Dates, calendars and domain modelling. `java.time` is the best date library any of the three has, and records make the domain almost declarative. |

## What they do

**`cutlist-cpp` — fabric cutting plan.** Given bolts of cloth and a list of
garment pieces, which pieces come off which bolt. It minimises bolts opened,
and then does the thing a textbook bin-packer will not: it gathers the leftover
into *one long remnant* instead of scattering it. Six half-metre offcuts are
rubbish; one three-metre remnant is a child's kameez.

**`barcode-rs` — Code 128 that actually scans.** An encoder *and a decoder*,
because the decoder is how you prove the encoder is right. It also decodes the
output of the app's existing `app/services/barcode_service.py`, which turns out
not to be a valid barcode at all — see that project's README.

**`scheduler-java` — can the shop keep its promises?** Given orders with
delivery dates and estimated hours, and tailors with daily capacity and skills,
it works out who cuts what and which delivery dates are not physically
reachable. The desktop app lets you promise six suits for Friday to one man who
works seven hours a day and records it without a murmur.

## Building

```sh
./build.sh            # all three, then run every test suite
```

Or individually — each is one compiler invocation, no package manager:

```sh
# C++
g++ -std=c++20 -O2 -Wall -Wextra -o cutlist cutlist-cpp/cutlist.cpp
./cutlist --selftest

# Rust  (rustc directly; see the note below about cargo on this machine)
rustc --edition 2021 --test barcode-rs/src/lib.rs -o rs_tests && ./rs_tests

# Java
javac -d scheduler-java/out scheduler-java/src/jtq/*.java
java -cp scheduler-java/out jtq.Main --selftest
```

## Toolchains, as installed on this machine

Nothing but a JDK was present, so the first two were installed via `winget`:

- **Java** — already here: Android Studio ships a JDK at
  `C:\Program Files\Android\Android Studio\jbr\bin`. Java 25.
- **C++** — `winget install BrechtSanders.WinLibs.POSIX.UCRT`, a standalone
  MinGW-w64 GCC 16.2. Lands in
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_*\mingw64\bin`.
- **Rust** — `winget install Rustlang.Rustup`, then
  `rustup toolchain install stable-x86_64-pc-windows-gnu` and
  `rustup default stable-x86_64-pc-windows-gnu`. The GNU toolchain pairs with
  the MinGW GCC above, which avoids needing the multi-gigabyte MSVC Build
  Tools.

### Two things about this machine specifically

**Smart App Control is on.** (`VerifiedAndReputablePolicyState = 1`, code
integrity enforcement = 2.) It blocks unsigned executables by reputation, and a
binary you compiled thirty seconds ago has none. In practice:

- `cargo` is blocked outright — *"An Application Control policy has blocked
  this file (os error 4551)"* — which is why the Rust build here calls `rustc`
  directly. `rustc` itself runs fine.
- Freshly compiled binaries are blocked when launched from PowerShell but run
  from Git Bash. That is inconsistent rather than principled, so `build.sh` is
  a shell script and everything here is driven from Bash.

Turning Smart App Control off is **not** recommended and was not done: on
Windows it is a one-way switch, and turning it back on requires reinstalling
Windows. If it starts blocking these binaries from Bash too, the options are to
sign them or to move the work into WSL (not currently installed).

**Build outputs are gitignored** — `*.exe`, `*.rlib`, `out/`, `target/`. Only
source is committed.
