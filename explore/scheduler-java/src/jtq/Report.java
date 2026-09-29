package jtq;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Turns a {@link Scheduler.Result} into the JSON document the tool prints. */
public final class Report {

    public static Map<String, Object> build(Scheduler.Result result,
                                            List<Scheduler.Tailor> tailors) {
        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("start", result.shop().from().toString());
        doc.put("summary", summary(result));
        doc.put("schedule", schedule(result));
        doc.put("tailors", tailorLoad(result, tailors));
        doc.put("problems", problems(result));
        return doc;
    }

    private static Map<String, Object> summary(Scheduler.Result result) {
        Map<String, Object> s = new LinkedHashMap<>();
        double hours = result.assignments().stream()
                .mapToDouble(a -> a.order().hours()).sum();
        s.put("ordersScheduled", result.assignments().size());
        s.put("ordersLate", result.lateAssignments().size());
        s.put("ordersUnassignable", result.unassignable().size());
        s.put("totalHours", hours);
        result.assignments().stream()
                .map(Scheduler.Assignment::finish)
                .max(LocalDate::compareTo)
                .ifPresent(last -> s.put("lastFinish", last.toString()));
        return s;
    }

    private static List<Object> schedule(Scheduler.Result result) {
        List<Object> rows = new ArrayList<>();
        // Print in the order the work actually happens, not the order it was
        // fed in -- this list is meant to be read next to the cutting table.
        result.assignments().stream()
                .sorted((a, b) -> {
                    int c = a.start().compareTo(b.start());
                    return c != 0 ? c : a.order().id().compareTo(b.order().id());
                })
                .forEach(a -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("order", a.order().id());
                    row.put("customer", a.order().customer());
                    row.put("garment", a.order().garment());
                    row.put("tailor", a.tailor().name());
                    row.put("hours", a.order().hours());
                    row.put("start", a.start().toString());
                    row.put("finish", a.finish().toString());
                    row.put("due", a.order().due() == null ? null : a.order().due().toString());
                    row.put("late", a.late());
                    if (a.late()) row.put("daysLate", (double) a.daysLate());
                    rows.add(row);
                });
        return rows;
    }

    private static List<Object> tailorLoad(Scheduler.Result result,
                                           List<Scheduler.Tailor> tailors) {
        LocalDate last = result.assignments().stream()
                .map(Scheduler.Assignment::finish)
                .max(LocalDate::compareTo)
                .orElse(result.shop().from());
        long workingDays = Scheduler.workingDaysBetween(result.shop(), last);

        List<Object> rows = new ArrayList<>();
        for (Scheduler.Tailor t : tailors) {
            double booked = result.hoursByTailor().getOrDefault(t.id(), 0.0);
            double available = workingDays * t.hoursPerDay();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", t.id());
            row.put("name", t.name());
            row.put("hoursPerDay", t.hoursPerDay());
            row.put("bookedHours", booked);
            row.put("availableHours", available);
            row.put("utilisationPct", available <= 0 ? 0.0 : (booked / available) * 100.0);
            row.put("orders", result.assignments().stream()
                    .filter(a -> a.tailor().id().equals(t.id()))
                    .map(a -> a.order().id())
                    .toList());
            rows.add(row);
        }
        return rows;
    }

    private static List<Object> problems(Scheduler.Result result) {
        List<Object> out = new ArrayList<>();
        for (Scheduler.Assignment a : result.lateAssignments()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("kind", "late");
            row.put("order", a.order().id());
            row.put("customer", a.order().customer());
            row.put("promised", a.order().due().toString());
            row.put("earliestPossible", a.finish().toString());
            row.put("daysLate", (double) a.daysLate());
            row.put("note", "not enough capacity before the promised date");
            out.add(row);
        }
        for (Scheduler.Order o : result.unassignable()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("kind", "unassignable");
            row.put("order", o.id());
            row.put("customer", o.customer());
            row.put("note", o.skill() == null || o.skill().isBlank()
                    ? "no tailor has capacity for this within a year"
                    : "no tailor on duty has the skill: " + o.skill());
            out.add(row);
        }
        return out;
    }

    public static String summaryLine(Scheduler.Result result) {
        return "%d scheduled, %d will miss their date, %d cannot be placed".formatted(
                result.assignments().size(),
                result.lateAssignments().size(),
                result.unassignable().size());
    }

    private Report() {}
}
