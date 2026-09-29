package jtq;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Assertions, run with {@code --selftest}. No JUnit: the point of this
 * exploration is a single {@code javac} and no downloads.
 */
public final class SelfTest {

    private static int passed;
    private static final List<String> failures = new ArrayList<>();

    public static boolean run() {
        jsonRoundTrips();
        jsonRejectsGarbage();
        capacityIsRespected();
        closedDaysAreSkipped();
        earliestDueDateWins();
        skillsAreHonoured();
        latenessIsReported();
        workIsSpreadAcrossTailors();
        impossibleWorkIsFlagged();
        zeroCapacityDoesNotHang();

        System.out.println();
        System.out.println(failures.isEmpty()
                ? "all " + passed + " checks passed"
                : passed + " passed, " + failures.size() + " FAILED");
        failures.forEach(f -> System.out.println("  FAIL " + f));
        return failures.isEmpty();
    }

    // ---- the checks -------------------------------------------------------

    static void jsonRoundTrips() {
        String text = """
                {"a": 1, "b": [true, false, null, "x\\ny"], "c": {"d": -2.5}}""";
        Object parsed = Json.parse(text);
        Object again = Json.parse(Json.write(parsed));
        check("JSON survives a write/parse round trip", Json.write(parsed).equals(Json.write(again)));

        Map<?, ?> m = (Map<?, ?>) parsed;
        check("JSON keeps a nested string with an escape",
                ((List<?>) m.get("b")).get(3).equals("x\ny"));
        check("JSON keeps a negative fraction",
                ((Map<?, ?>) m.get("c")).get("d").equals(-2.5));
        check("whole numbers print without a decimal point",
                Json.write(Map.of("n", 3.0)).contains("\"n\": 3"));
    }

    static void jsonRejectsGarbage() {
        for (String bad : new String[]{"{", "{\"a\" 1}", "[1,]}", "tru", "{\"a\":1} trailing"}) {
            boolean threw = false;
            try {
                Json.parse(bad);
            } catch (RuntimeException e) {
                threw = true;
            }
            check("JSON rejects " + bad.replace("\n", " "), threw);
        }
    }

    static void capacityIsRespected() {
        // 24 hours of work for one tailor doing 8 a day, starting Monday,
        // must finish on the third working day and not before.
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var t = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        var o = order("ORD-1", 24, LocalDate.of(2026, 3, 1));
        var r = Scheduler.plan(List.of(o), List.of(t), shop);

        check("a 24 hour job at 8 hours a day takes three days",
                r.assignments().getFirst().finish().equals(LocalDate.of(2026, 2, 4)));
        check("and it starts on day one",
                r.assignments().getFirst().start().equals(LocalDate.of(2026, 2, 2)));
    }

    static void closedDaysAreSkipped() {
        // Monday start, shop shut Tuesday and Wednesday: 16 hours of work
        // lands on Monday and Thursday.
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2),
                EnumSet.of(DayOfWeek.MONDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY));
        var t = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        var r = Scheduler.plan(List.of(order("ORD-1", 16, null)), List.of(t), shop);
        check("work skips the days the shop is closed",
                r.assignments().getFirst().finish().equals(LocalDate.of(2026, 2, 5)));
    }

    static void earliestDueDateWins() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var t = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        // Fed in the wrong order on purpose.
        var late = order("ORD-LATE", 8, LocalDate.of(2026, 2, 20));
        var soon = order("ORD-SOON", 8, LocalDate.of(2026, 2, 3));
        var r = Scheduler.plan(List.of(late, soon), List.of(t), shop);

        var first = r.assignments().stream()
                .min((a, b) -> a.start().compareTo(b.start())).orElseThrow();
        check("the order due first is cut first", first.order().id().equals("ORD-SOON"));
        check("neither order is late with capacity for both",
                r.lateAssignments().isEmpty());
    }

    static void skillsAreHonoured() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var generalist = new Scheduler.Tailor("T1", "Ali", 8, Set.of("kameez"));
        var specialist = new Scheduler.Tailor("T2", "Usman", 8, Set.of("sherwani"));
        var o = new Scheduler.Order("ORD-1", "Farman", "Sherwani", 8,
                LocalDate.of(2026, 3, 1), 0, "sherwani");
        var r = Scheduler.plan(List.of(o), List.of(generalist, specialist), shop);

        check("a skilled job goes to the tailor who has the skill",
                r.assignments().getFirst().tailor().id().equals("T2"));

        // Nobody with the skill at all.
        var r2 = Scheduler.plan(List.of(o), List.of(generalist), shop);
        check("a job nobody can do is reported, not silently dropped",
                r2.assignments().isEmpty() && r2.unassignable().size() == 1);
        check("and the reason names the missing skill",
                Json.write(Report.build(r2, List.of(generalist))).contains("sherwani"));
    }

    static void latenessIsReported() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var t = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        // 40 hours promised for tomorrow: five days of work, four days late.
        var o = order("ORD-1", 40, LocalDate.of(2026, 2, 3));
        var r = Scheduler.plan(List.of(o), List.of(t), shop);
        var a = r.assignments().getFirst();

        check("an impossible promise is marked late", a.late());
        check("by the right number of days", a.daysLate() == 3);
        check("the report explains it", Json.write(Report.build(r, List.of(t)))
                .contains("not enough capacity"));
    }

    static void workIsSpreadAcrossTailors() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var a = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        var b = new Scheduler.Tailor("T2", "Usman", 8, Set.of());
        List<Scheduler.Order> orders = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            orders.add(order("ORD-" + i, 8, LocalDate.of(2026, 2, 20)));
        }
        var r = Scheduler.plan(orders, List.of(a, b), shop);

        check("two idle tailors both get work",
                r.hoursByTailor().get("T1") > 0 && r.hoursByTailor().get("T2") > 0);
        check("and the split is even",
                r.hoursByTailor().get("T1").equals(r.hoursByTailor().get("T2")));
        check("every hour is accounted for",
                r.hoursByTailor().values().stream().mapToDouble(Double::doubleValue).sum() == 32.0);
    }

    static void impossibleWorkIsFlagged() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var t = new Scheduler.Tailor("T1", "Ali", 8, Set.of());
        // More than a year of work for one person.
        var r = Scheduler.plan(List.of(order("ORD-1", 8 * 400, null)), List.of(t), shop);
        check("work that does not fit the horizon is unassignable",
                r.assignments().isEmpty() && r.unassignable().size() == 1);
    }

    static void zeroCapacityDoesNotHang() {
        var shop = new Scheduler.Shop(LocalDate.of(2026, 2, 2), everyDay());
        var idle = new Scheduler.Tailor("T1", "On leave", 0, Set.of());
        var r = Scheduler.plan(List.of(order("ORD-1", 8, null)), List.of(idle), shop);
        check("a tailor with no hours cannot be assigned work",
                r.assignments().isEmpty() && r.unassignable().size() == 1);

        var noDays = new Scheduler.Shop(LocalDate.of(2026, 2, 2), EnumSet.noneOf(DayOfWeek.class));
        var r2 = Scheduler.plan(List.of(order("ORD-1", 8, null)),
                List.of(new Scheduler.Tailor("T1", "Ali", 8, Set.of())), noDays);
        check("a shop that is never open schedules nothing, without hanging",
                r2.assignments().isEmpty());
    }

    // ---- helpers ----------------------------------------------------------

    private static Scheduler.Order order(String id, double hours, LocalDate due) {
        return new Scheduler.Order(id, "Farman Saim", "Shalwar Kameez", hours, due, 0, null);
    }

    private static Set<DayOfWeek> everyDay() {
        return EnumSet.allOf(DayOfWeek.class);
    }

    private static void check(String name, boolean ok) {
        if (ok) {
            passed++;
            System.out.println("PASS  " + name);
        } else {
            failures.add(name);
            System.out.println("FAIL  " + name);
        }
    }

    private SelfTest() {}
}
