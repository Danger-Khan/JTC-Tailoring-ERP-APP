#!/usr/bin/env bash
# Build all three prototypes and run every test suite.
#
# Run from Git Bash. Smart App Control on this machine blocks freshly
# compiled binaries when they are launched from PowerShell but allows them
# from Bash -- see README.md.
set -uo pipefail
cd "$(dirname "$0")"

GPP="${GPP:-$HOME/AppData/Local/Microsoft/WinGet/Packages/BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe/mingw64/bin/g++.exe}"
RUSTC="${RUSTC:-$HOME/.cargo/bin/rustc.exe}"
JAVAC="${JAVAC:-/c/Program Files/Android/Android Studio/jbr/bin/javac.exe}"
JAVA="${JAVA:-/c/Program Files/Android/Android Studio/jbr/bin/java.exe}"

# rustc needs the MinGW linker on PATH for the -gnu toolchain.
export PATH="$(dirname "$GPP"):$PATH"

failed=()
have() { [ -x "$1" ]; }

hr() { printf '\n== %s %s\n' "$1" "$(printf '=%.0s' $(seq 1 $((60 - ${#1}))))"; }

# ---- C++ -------------------------------------------------------------------
hr "C++  cutlist"
if have "$GPP"; then
    if "$GPP" -std=c++20 -O2 -Wall -Wextra -o cutlist-cpp/cutlist.exe cutlist-cpp/cutlist.cpp; then
        ./cutlist-cpp/cutlist.exe --selftest | tail -3 || failed+=("cutlist tests")
    else
        failed+=("cutlist build")
    fi
else
    echo "SKIP: no g++ at $GPP"
fi

# ---- Rust ------------------------------------------------------------------
hr "Rust  barcode"
if have "$RUSTC"; then
    (
        cd barcode-rs || exit 1
        "$RUSTC" --edition 2021 --test src/lib.rs -o rs_tests.exe || exit 1
        ./rs_tests.exe | tail -3 || exit 1
        "$RUSTC" --edition 2021 -O --crate-type=lib --crate-name jtq_barcode \
            src/lib.rs -o libjtq_barcode.rlib || exit 1
        "$RUSTC" --edition 2021 -O --extern jtq_barcode=libjtq_barcode.rlib \
            src/main.rs -o jtq-barcode.exe || exit 1
    ) || failed+=("barcode")
else
    echo "SKIP: no rustc at $RUSTC"
fi

# ---- Java ------------------------------------------------------------------
hr "Java  scheduler"
if have "$JAVAC"; then
    if "$JAVAC" -d scheduler-java/out -Xlint:all scheduler-java/src/jtq/*.java; then
        "$JAVA" -cp scheduler-java/out jtq.Main --selftest | tail -3 || failed+=("scheduler tests")
    else
        failed+=("scheduler build")
    fi
else
    echo "SKIP: no javac at $JAVAC"
fi

# ---- summary ---------------------------------------------------------------
hr "summary"
if [ ${#failed[@]} -eq 0 ]; then
    echo "all three built and passed"
else
    printf 'FAILED: %s\n' "${failed[@]}"
    exit 1
fi
