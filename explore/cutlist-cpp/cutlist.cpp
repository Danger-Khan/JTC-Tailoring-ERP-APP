// Fabric cutting plan: which pieces come off which bolt of cloth.
//
// A tailoring shop buys cloth in bolts (thaan) of a fixed length and cuts
// garment pieces from them. Cut carelessly and you use an extra bolt you did
// not need, or -- worse and much more common -- you end up with the same
// total waste spread over six half-metre offcuts instead of gathered into
// one three-metre remnant. Six offcuts are rubbish. A three-metre remnant is
// a child's kameez.
//
// So this optimises two things, in order:
//   1. the number of bolts opened (fewer is strictly better), then
//   2. the length of the single longest remnant (longer is strictly better),
//      given the same number of bolts.
//
// That second objective is the part a textbook bin-packer will not do for
// you, and it is the one the shop actually feels.
//
// Build:  g++ -std=c++20 -O2 -Wall -Wextra -o cutlist cutlist.cpp
// Test:   ./cutlist --selftest
// Use:    ./cutlist --in cutlist.txt [--json]

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

namespace cutlist {

struct Piece {
    std::string id;
    double meters = 0.0;
};

struct Bolt {
    std::vector<Piece> pieces;
    double used = 0.0;

    double remnant(double bolt_length) const { return bolt_length - used; }
};

struct Problem {
    double bolt_length = 50.0;
    double kerf = 0.0;  // allowance lost to each cut (seam, straightening)
    std::vector<Piece> pieces;
};

struct Plan {
    std::vector<Bolt> bolts;
    double bolt_length = 0.0;
    std::vector<Piece> unplaceable;  // a single piece longer than a whole bolt

    std::size_t bolts_used() const { return bolts.size(); }

    double total_waste() const {
        double sum = 0.0;
        for (const Bolt& b : bolts) sum += b.remnant(bolt_length);
        return sum;
    }

    double longest_remnant() const {
        double best = 0.0;
        for (const Bolt& b : bolts) best = std::max(best, b.remnant(bolt_length));
        return best;
    }

    // Offcuts too short to be worth keeping. The shop's own threshold; 0.5m
    // is about the least you can make anything from.
    int scrap_offcuts(double keep_threshold = 0.5) const {
        int n = 0;
        for (const Bolt& b : bolts) {
            double r = b.remnant(bolt_length);
            if (r > 1e-9 && r < keep_threshold) n++;
        }
        return n;
    }
};

// ---------------------------------------------------------------------------
// Packing
// ---------------------------------------------------------------------------

// No plan can use fewer bolts than this. Lets the report say whether the
// answer is provably optimal on bolt count rather than merely good.
std::size_t lower_bound_bolts(const Problem& p) {
    double total = 0.0;
    for (const Piece& piece : p.pieces) total += piece.meters + p.kerf;
    if (total <= 1e-9) return 0;
    return static_cast<std::size_t>(std::ceil(total / p.bolt_length - 1e-9));
}

// First-Fit-Decreasing. Longest piece first into the first bolt it fits;
// the classic result is that this never uses more than 11/9 of the optimal
// bolt count, and on realistic cut lists it usually hits the bound exactly.
Plan pack_ffd(const Problem& p) {
    Plan plan;
    plan.bolt_length = p.bolt_length;

    std::vector<Piece> sorted = p.pieces;
    std::stable_sort(sorted.begin(), sorted.end(),
                     [](const Piece& a, const Piece& b) { return a.meters > b.meters; });

    for (const Piece& piece : sorted) {
        const double need = piece.meters + p.kerf;
        if (need > p.bolt_length + 1e-9) {
            plan.unplaceable.push_back(piece);
            continue;
        }
        bool placed = false;
        for (Bolt& bolt : plan.bolts) {
            if (bolt.used + need <= p.bolt_length + 1e-9) {
                bolt.pieces.push_back(piece);
                bolt.used += need;
                placed = true;
                break;
            }
        }
        if (!placed) {
            Bolt bolt;
            bolt.pieces.push_back(piece);
            bolt.used = need;
            plan.bolts.push_back(std::move(bolt));
        }
    }
    return plan;
}

// How good a set of bolts is, in the order the shop cares: fewer bolts
// first, then the longest single remnant. Compared lexicographically.
struct Score {
    std::size_t bolts;
    double longest_remnant;

    bool better_than(const Score& other) const {
        if (bolts != other.bolts) return bolts < other.bolts;
        return longest_remnant > other.longest_remnant + 1e-9;
    }
};

Score score_of(const std::vector<Bolt>& bolts, double bolt_length) {
    Score s{0, 0.0};
    for (const Bolt& b : bolts) {
        if (b.pieces.empty()) continue;
        s.bolts++;
        s.longest_remnant = std::max(s.longest_remnant, bolt_length - b.used);
    }
    return s;
}

// Same total waste, gathered instead of scattered: move one piece at a time
// and keep the move only if the score actually improves.
//
// The improvement test is the entire algorithm. An earlier version moved a
// piece to wherever it fit best and assumed that had to help -- it did not,
// and on the sample cut list it turned a 10.2m remnant into a 9.3m one
// while reporting success. Hill climbing without checking you went uphill
// is just walking.
//
// Termination is then free: every accepted move strictly improves a score
// that is bounded below (bolt count) and above (remnant length).
void concentrate_remnant(Plan& plan, double kerf) {
    Score best = score_of(plan.bolts, plan.bolt_length);
    bool improved = true;
    int guard = 0;

    while (improved && guard++ < 1000) {
        improved = false;

        for (std::size_t from = 0; from < plan.bolts.size() && !improved; ++from) {
            for (std::size_t i = 0; i < plan.bolts[from].pieces.size() && !improved; ++i) {
                for (std::size_t to = 0; to < plan.bolts.size() && !improved; ++to) {
                    if (to == from) continue;

                    const Piece piece = plan.bolts[from].pieces[i];
                    const double need = piece.meters + kerf;
                    if (plan.bolts[to].used + need > plan.bolt_length + 1e-9) continue;

                    std::vector<Bolt> trial = plan.bolts;
                    trial[to].pieces.push_back(piece);
                    trial[to].used += need;
                    trial[from].pieces.erase(trial[from].pieces.begin() +
                                             static_cast<std::ptrdiff_t>(i));
                    trial[from].used -= need;

                    Score candidate = score_of(trial, plan.bolt_length);
                    if (!candidate.better_than(best)) continue;

                    trial.erase(std::remove_if(trial.begin(), trial.end(),
                                               [](const Bolt& b) { return b.pieces.empty(); }),
                                trial.end());
                    plan.bolts = std::move(trial);
                    best = candidate;
                    improved = true;
                }
            }
        }
    }

    // Present fullest first: the last bolt is then the one with the remnant
    // worth keeping, which is how it gets written on the shelf.
    std::stable_sort(plan.bolts.begin(), plan.bolts.end(),
                     [](const Bolt& a, const Bolt& b) { return a.used > b.used; });
}

Plan solve(const Problem& p, bool concentrate = true) {
    Plan plan = pack_ffd(p);
    if (concentrate) concentrate_remnant(plan, p.kerf);
    return plan;
}

// ---------------------------------------------------------------------------
// Input
// ---------------------------------------------------------------------------
//
//   bolt 50          # bolt length in meters
//   kerf 0.05        # allowance per cut, optional
//   ORD-101 3.5      # piece id, meters
//
Problem parse(std::istream& in, std::string* error) {
    Problem p;
    std::string line;
    int line_no = 0;

    while (std::getline(in, line)) {
        ++line_no;
        if (auto hash = line.find('#'); hash != std::string::npos) line.erase(hash);
        std::istringstream ls(line);
        std::string first;
        if (!(ls >> first)) continue;

        if (first == "bolt" || first == "kerf") {
            double value = 0.0;
            if (!(ls >> value)) {
                if (error) *error = "line " + std::to_string(line_no) + ": " + first +
                                    " needs a number";
                return p;
            }
            (first == "bolt" ? p.bolt_length : p.kerf) = value;
            continue;
        }

        double meters = 0.0;
        if (!(ls >> meters)) {
            if (error) *error = "line " + std::to_string(line_no) +
                                ": expected '<id> <meters>', got '" + first + "'";
            return p;
        }
        if (meters <= 0.0) {
            if (error) *error = "line " + std::to_string(line_no) + ": " + first +
                                " needs a positive length";
            return p;
        }
        p.pieces.push_back(Piece{first, meters});
    }
    return p;
}

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------

void print_human(const Plan& plan, const Problem& p, std::ostream& out) {
    const std::size_t bound = lower_bound_bolts(p);
    out << std::fixed << std::setprecision(2);
    out << "Bolt length      : " << p.bolt_length << " m\n";
    if (p.kerf > 0) out << "Cutting allowance: " << p.kerf << " m per piece\n";
    out << "Pieces           : " << p.pieces.size() << "\n";
    out << "Bolts to open    : " << plan.bolts_used() << "  (lower bound " << bound
        << (plan.bolts_used() == bound ? ", optimal)" : ", could not reach the bound)") << "\n";
    out << "Total waste      : " << plan.total_waste() << " m\n";
    out << "Longest remnant  : " << plan.longest_remnant() << " m  (keep this one)\n";
    out << "Unusable offcuts : " << plan.scrap_offcuts() << "  (under 0.50 m)\n\n";

    std::size_t n = 1;
    for (const Bolt& bolt : plan.bolts) {
        out << "Bolt " << n++ << "  used " << bolt.used << " m, left "
            << bolt.remnant(plan.bolt_length) << " m\n";
        for (const Piece& piece : bolt.pieces) {
            out << "    " << std::left << std::setw(14) << piece.id << std::right
                << std::setw(7) << piece.meters << " m\n";
        }
    }
    if (!plan.unplaceable.empty()) {
        out << "\nWill not fit on any bolt:\n";
        for (const Piece& piece : plan.unplaceable) {
            out << "    " << piece.id << " needs " << piece.meters
                << " m but a bolt is only " << p.bolt_length << " m\n";
        }
    }
}

void print_json(const Plan& plan, const Problem& p, std::ostream& out) {
    out << std::fixed << std::setprecision(3);
    out << "{\n  \"boltLength\": " << p.bolt_length
        << ",\n  \"kerf\": " << p.kerf
        << ",\n  \"boltsUsed\": " << plan.bolts_used()
        << ",\n  \"lowerBound\": " << lower_bound_bolts(p)
        << ",\n  \"optimalBoltCount\": "
        << (plan.bolts_used() == lower_bound_bolts(p) ? "true" : "false")
        << ",\n  \"totalWaste\": " << plan.total_waste()
        << ",\n  \"longestRemnant\": " << plan.longest_remnant()
        << ",\n  \"scrapOffcuts\": " << plan.scrap_offcuts()
        << ",\n  \"bolts\": [\n";
    for (std::size_t i = 0; i < plan.bolts.size(); ++i) {
        const Bolt& bolt = plan.bolts[i];
        out << "    { \"used\": " << bolt.used
            << ", \"remnant\": " << bolt.remnant(plan.bolt_length) << ", \"pieces\": [";
        for (std::size_t j = 0; j < bolt.pieces.size(); ++j) {
            out << "{\"id\": \"" << bolt.pieces[j].id << "\", \"meters\": "
                << bolt.pieces[j].meters << "}";
            if (j + 1 < bolt.pieces.size()) out << ", ";
        }
        out << "] }" << (i + 1 < plan.bolts.size() ? "," : "") << "\n";
    }
    out << "  ]\n}\n";
}

}  // namespace cutlist

// ---------------------------------------------------------------------------
// Self-test
// ---------------------------------------------------------------------------

namespace {

int checks_passed = 0;
std::vector<std::string> failures;

void check(const std::string& name, bool ok) {
    if (ok) {
        ++checks_passed;
        std::cout << "PASS  " << name << "\n";
    } else {
        failures.push_back(name);
        std::cout << "FAIL  " << name << "\n";
    }
}

cutlist::Problem make(double bolt, std::vector<double> lengths, double kerf = 0.0) {
    cutlist::Problem p;
    p.bolt_length = bolt;
    p.kerf = kerf;
    for (std::size_t i = 0; i < lengths.size(); ++i) {
        p.pieces.push_back({"P" + std::to_string(i), lengths[i]});
    }
    return p;
}

// Every piece placed exactly once, and no bolt over its length.
bool plan_is_sound(const cutlist::Plan& plan, const cutlist::Problem& p) {
    std::size_t placed = plan.unplaceable.size();
    for (const cutlist::Bolt& bolt : plan.bolts) {
        double sum = 0.0;
        for (const cutlist::Piece& piece : bolt.pieces) sum += piece.meters + p.kerf;
        if (sum > p.bolt_length + 1e-6) return false;
        if (std::abs(sum - bolt.used) > 1e-6) return false;
        placed += bolt.pieces.size();
    }
    return placed == p.pieces.size();
}

int self_test() {
    using namespace cutlist;

    {
        Problem p = make(10, {4, 4, 4});
        Plan plan = solve(p);
        check("three 4m pieces need two 10m bolts", plan.bolts_used() == 2);
        check("and that is the proven lower bound", plan.bolts_used() == lower_bound_bolts(p));
        check("every piece is placed exactly once", plan_is_sound(plan, p));
    }
    {
        // The whole point: same waste either way, but gathered not scattered.
        Problem p = make(10, {5, 5, 3, 3, 2, 2});
        Plan plan = solve(p);
        check("a perfect fit uses exactly two bolts", plan.bolts_used() == 2);
        check("a perfect fit leaves no waste", std::abs(plan.total_waste()) < 1e-6);
    }
    {
        Problem p = make(10, {6, 3, 3, 3});
        Plan plan = solve(p);
        check("waste ends up in one remnant, not spread thin",
              plan.longest_remnant() > 4.0 - 1e-6);
        check("so nothing becomes an unusable offcut", plan.scrap_offcuts() == 0);
        check("the plan is still sound after redistribution", plan_is_sound(plan, p));
    }
    {
        // The regression. Gathering the remnant must never come out behind
        // plain first-fit -- the first version of it did exactly that, and
        // turned a 10.2m remnant into a 9.3m one while reporting success.
        // Anything that only checks "is the plan valid" sails past this.
        const std::vector<std::vector<double>> cases = {
            {6.5, 2.4, 1.6, 11.0, 6.2, 8.5, 6.4, 6.0, 10.5, 2.2, 6.3, 1.7, 9.0, 6.1, 2.5},
            {4, 4, 4, 4, 4, 4, 4},
            {9, 8, 7, 6, 5, 4, 3, 2, 1},
            {1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7},
            {50, 25, 25, 12.5, 12.5, 12.5},
        };
        bool never_worse = true;
        bool sometimes_better = false;
        for (const std::vector<double>& lengths : cases) {
            Problem p = make(50, lengths, 0.1);
            Plan tuned = solve(p, true);
            Plan plain = solve(p, false);
            if (tuned.bolts_used() > plain.bolts_used()) never_worse = false;
            if (tuned.bolts_used() == plain.bolts_used()
                && tuned.longest_remnant() + 1e-6 < plain.longest_remnant()) {
                never_worse = false;
            }
            if (tuned.longest_remnant() > plain.longest_remnant() + 1e-6
                || tuned.bolts_used() < plain.bolts_used()) {
                sometimes_better = true;
            }
            if (!plan_is_sound(tuned, p)) never_worse = false;
        }
        check("gathering the remnant is never worse than plain first-fit", never_worse);
        check("and on at least one cut list it is better", sometimes_better);
    }
    {
        Problem p = make(10, {12, 3});
        Plan plan = solve(p);
        check("a piece longer than a bolt is reported, not silently dropped",
              plan.unplaceable.size() == 1 && plan.unplaceable[0].meters == 12);
        check("the rest is still planned", plan.bolts_used() == 1);
    }
    {
        // 12m bolt, not 10: with the allowance each 3m piece costs 3.5m, so
        // three of them need 10.5m and would not fit a 10m bolt at all --
        // which is the whole reason to charge the allowance up front.
        Problem p = make(12, {3, 3, 3}, 0.5);
        Plan plan = solve(p);
        double used = plan.bolts.empty() ? 0.0 : plan.bolts[0].used;
        check("the cutting allowance is charged per piece",
              plan.bolts_used() == 1 && std::abs(used - (3 * 3.5)) < 1e-6);

        // The same three pieces without the allowance do fit a 10m bolt;
        // with it they need two. Forgetting the allowance is exactly how a
        // shop ends up one bolt short in the middle of a job.
        Problem tight = make(10, {3, 3, 3}, 0.5);
        check("the allowance can push a job onto another bolt",
              solve(tight).bolts_used() == 2 && solve(make(10, {3, 3, 3})).bolts_used() == 1);
        check("and the lower bound counts it too", lower_bound_bolts(tight) == 2);
    }
    {
        Problem p = make(10, {});
        Plan plan = solve(p);
        check("an empty cut list opens no bolts", plan.bolts_used() == 0);
        check("and has no lower bound to beat", lower_bound_bolts(p) == 0);
    }
    {
        // FFD's guarantee is 11/9 OPT + 6/9; check it holds on a nasty set
        // and that we never exceed the trivial one-piece-per-bolt fallback.
        Problem p = make(100, {51, 28, 28, 28, 27, 26, 26, 25, 24, 23, 22, 21});
        Plan plan = solve(p);
        std::size_t bound = lower_bound_bolts(p);
        check("a hard instance stays within the FFD guarantee",
              static_cast<double>(plan.bolts_used()) <= 11.0 / 9.0 * bound + 1.0);
        check("and never worse than one piece per bolt",
              plan.bolts_used() <= p.pieces.size());
        check("the hard instance is sound too", plan_is_sound(plan, p));
    }
    {
        // Parsing.
        std::istringstream in("bolt 40\nkerf 0.25\n# comment\nORD-1 3.5\nORD-2 2\n");
        std::string err;
        Problem p = parse(in, &err);
        check("parser reads the bolt length", std::abs(p.bolt_length - 40) < 1e-9);
        check("parser reads the kerf", std::abs(p.kerf - 0.25) < 1e-9);
        check("parser skips comments and blank lines", p.pieces.size() == 2);
        check("parser keeps piece ids", p.pieces[0].id == "ORD-1");
        check("clean input reports no error", err.empty());

        std::istringstream bad("bolt 40\nORD-1 notanumber\n");
        std::string err2;
        parse(bad, &err2);
        check("a bad length is an error, not a silent zero", !err2.empty());

        std::istringstream neg("ORD-1 -3\n");
        std::string err3;
        parse(neg, &err3);
        check("a negative length is rejected", !err3.empty());
    }

    std::cout << "\n"
              << (failures.empty() ? "all " + std::to_string(checks_passed) + " checks passed"
                                   : std::to_string(checks_passed) + " passed, " +
                                         std::to_string(failures.size()) + " FAILED")
              << "\n";
    for (const std::string& f : failures) std::cout << "  FAIL " << f << "\n";
    return failures.empty() ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    std::vector<std::string> args(argv + 1, argv + argc);
    auto has = [&](const std::string& flag) {
        return std::find(args.begin(), args.end(), flag) != args.end();
    };
    auto value_of = [&](const std::string& flag) -> std::optional<std::string> {
        auto it = std::find(args.begin(), args.end(), flag);
        if (it == args.end() || it + 1 == args.end()) return std::nullopt;
        return *(it + 1);
    };

    if (has("--selftest")) return self_test();

    std::string error;
    cutlist::Problem problem;
    if (auto path = value_of("--in")) {
        std::ifstream file(*path);
        if (!file) {
            std::cerr << "cannot open " << *path << "\n";
            return 2;
        }
        problem = cutlist::parse(file, &error);
    } else if (!args.empty() && args[0] == "-") {
        problem = cutlist::parse(std::cin, &error);
    } else {
        std::cerr <<
            "usage: cutlist --in <cutlist.txt> [--json]\n"
            "       cutlist - [--json]          read the cut list from stdin\n"
            "       cutlist --selftest\n\n"
            "Cut list format, one directive or piece per line:\n"
            "  bolt 50        bolt length in meters\n"
            "  kerf 0.05      allowance lost per cut (optional)\n"
            "  ORD-101 3.5    a piece: id, then meters\n";
        return 2;
    }

    if (!error.empty()) {
        std::cerr << "cut list: " << error << "\n";
        return 2;
    }

    cutlist::Plan plan = cutlist::solve(problem, !has("--plain"));
    if (has("--json")) {
        cutlist::print_json(plan, problem, std::cout);
    } else {
        cutlist::print_human(plan, problem, std::cout);

        // Show what the second objective bought, so it is a measurement
        // rather than a claim.
        if (!has("--plain")) {
            cutlist::Plan raw = cutlist::solve(problem, false);
            std::cout << "\nWithout gathering the remnant (--plain): "
                      << raw.bolts_used() << " bolts, longest remnant "
                      << raw.longest_remnant() << " m, "
                      << raw.scrap_offcuts() << " unusable offcuts\n";
        }
    }
    return plan.unplaceable.empty() ? 0 : 3;
}
