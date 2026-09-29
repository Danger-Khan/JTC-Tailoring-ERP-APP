package jtq;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Command line front end.
 *
 * <pre>
 *   java -cp out jtq.Main --in workshop.json [--out plan.json] [--start 2026-02-02]
 *   java -cp out jtq.Main --selftest
 * </pre>
 *
 * <p>Reads and writes JSON on purpose: nothing here touches the Excel files,
 * so it can be pointed at a copy of real data without any chance of writing
 * into the shop's books.
 */
public final class Main {

    public static void main(String[] args) throws Exception {
        Map<String, String> opts = parseArgs(args);

        if (opts.containsKey("selftest")) {
            System.exit(SelfTest.run() ? 0 : 1);
        }
        if (!opts.containsKey("in")) {
            System.err.println("""
                    usage: java -cp out jtq.Main --in <workshop.json> [--out <plan.json>] [--start YYYY-MM-DD]
                           java -cp out jtq.Main --selftest

                    The input file holds "tailors" and "orders"; see sample-workshop.json.
                    With no --out the plan is printed to stdout.""");
            System.exit(2);
        }

        String text = Files.readString(Path.of(opts.get("in")), StandardCharsets.UTF_8);
        Object root = Json.parse(text);
        if (!(root instanceof Map<?, ?> doc)) {
            System.err.println("the top level of the input must be a JSON object");
            System.exit(2);
            return;
        }

        LocalDate start = opts.containsKey("start")
                ? LocalDate.parse(opts.get("start"))
                : readDate(doc.get("start"), LocalDate.now());

        Scheduler.Shop shop = new Scheduler.Shop(start, readWorkingDays(doc.get("workingDays")));
        List<Scheduler.Tailor> tailors = readTailors(doc.get("tailors"));
        List<Scheduler.Order> orders = readOrders(doc.get("orders"));

        if (tailors.isEmpty()) {
            System.err.println("no tailors in the input; nothing can be scheduled");
            System.exit(1);
        }

        Scheduler.Result result = Scheduler.plan(orders, tailors, shop);
        String out = Json.write(Report.build(result, tailors));

        if (opts.containsKey("out")) {
            Files.writeString(Path.of(opts.get("out")), out + "\n", StandardCharsets.UTF_8);
            System.out.println("wrote " + opts.get("out"));
            System.out.println(Report.summaryLine(result));
        } else {
            System.out.println(out);
        }
        // A schedule that cannot keep its promises is worth a non-zero exit,
        // so this can sit in a nightly check and actually raise its hand.
        System.exit(result.lateAssignments().isEmpty() && result.unassignable().isEmpty() ? 0 : 3);
    }

    // ---- input ------------------------------------------------------------

    static List<Scheduler.Tailor> readTailors(Object node) {
        List<Scheduler.Tailor> out = new ArrayList<>();
        if (!(node instanceof List<?> list)) return out;
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> m)) continue;
            Set<String> skills = new LinkedHashSet<>();
            if (m.get("skills") instanceof List<?> raw) {
                for (Object s : raw) skills.add(String.valueOf(s));
            }
            out.add(new Scheduler.Tailor(
                    str(m.get("id"), "T-" + (out.size() + 1)),
                    str(m.get("name"), "(unnamed)"),
                    num(m.get("hoursPerDay"), 8.0),
                    skills));
        }
        return out;
    }

    static List<Scheduler.Order> readOrders(Object node) {
        List<Scheduler.Order> out = new ArrayList<>();
        if (!(node instanceof List<?> list)) return out;
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> m)) continue;
            out.add(new Scheduler.Order(
                    str(m.get("id"), "ORD-?"),
                    str(m.get("customer"), ""),
                    str(m.get("garment"), ""),
                    num(m.get("hours"), 0.0),
                    readDate(m.get("due"), null),
                    (int) num(m.get("priority"), 0.0),
                    m.get("skill") == null ? null : String.valueOf(m.get("skill"))));
        }
        return out;
    }

    static Set<DayOfWeek> readWorkingDays(Object node) {
        if (!(node instanceof List<?> list) || list.isEmpty()) {
            return EnumSet.complementOf(EnumSet.of(DayOfWeek.SUNDAY));
        }
        Set<DayOfWeek> days = EnumSet.noneOf(DayOfWeek.class);
        for (Object d : list) {
            days.add(DayOfWeek.valueOf(String.valueOf(d).trim().toUpperCase()));
        }
        return days;
    }

    static LocalDate readDate(Object node, LocalDate fallback) {
        if (node == null) return fallback;
        String s = String.valueOf(node).trim();
        if (s.isEmpty()) return fallback;
        try {
            return LocalDate.parse(s);
        } catch (RuntimeException e) {
            return fallback;
        }
    }

    static String str(Object node, String fallback) {
        return node == null ? fallback : String.valueOf(node);
    }

    static double num(Object node, double fallback) {
        if (node instanceof Number n) return n.doubleValue();
        if (node == null) return fallback;
        try {
            return Double.parseDouble(String.valueOf(node));
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    static Map<String, String> parseArgs(String[] args) {
        Map<String, String> opts = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (!a.startsWith("--")) continue;
            String key = a.substring(2);
            if (i + 1 < args.length && !args[i + 1].startsWith("--")) {
                opts.put(key, args[++i]);
            } else {
                opts.put(key, "");
            }
        }
        return opts;
    }

    private Main() {}
}
