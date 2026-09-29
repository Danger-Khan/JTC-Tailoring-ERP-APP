package jtq;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Work out which tailor cuts which order, and which delivery dates the shop
 * cannot actually make.
 *
 * <p>The desktop app lets you type a delivery date and assign a tailor, and
 * nothing anywhere checks whether the two are compatible. Promise six suits
 * for Friday to one man who works seven hours a day and the app records it
 * happily. This works the schedule out from capacity and says which promises
 * will break, and by how many days, while there is still time to move them.
 *
 * <p>Earliest-due-date first, which is the classic result for this shape of
 * problem: if any order sequence on a single machine can meet every deadline,
 * sorting by deadline meets every deadline too. With several tailors it is a
 * heuristic rather than a guarantee, so the report always states the gap it
 * could not close instead of quietly picking a winner.
 */
public final class Scheduler {

    /** How far ahead to look before calling an order unschedulable. */
    private static final int HORIZON_DAYS = 365;

    public record Tailor(String id, String name, double hoursPerDay, Set<String> skills) {
        public boolean canDo(String skill) {
            return skill == null || skill.isBlank() || skills.isEmpty() || skills.contains(skill);
        }
    }

    public record Order(String id, String customer, String garment, double hours,
                        LocalDate due, int priority, String skill) {}

    public record Assignment(Order order, Tailor tailor, LocalDate start, LocalDate finish,
                             long daysLate) {
        public boolean late() {
            return daysLate > 0;
        }
    }

    public record Shop(LocalDate from, Set<DayOfWeek> workingDays) {
        public static Shop defaults(LocalDate from) {
            // Friday is the short day in most Pakistani tailoring shops and
            // Sunday is closed; both are configurable in the input file.
            return new Shop(from, EnumSet.complementOf(EnumSet.of(DayOfWeek.SUNDAY)));
        }

        public boolean isWorkingDay(LocalDate day) {
            return workingDays.contains(day.getDayOfWeek());
        }
    }

    public record Result(List<Assignment> assignments, List<Order> unassignable,
                         Map<String, Double> hoursByTailor, Shop shop) {

        public List<Assignment> lateAssignments() {
            return assignments.stream().filter(Assignment::late).toList();
        }
    }

    /** A tailor's booked hours, day by day. */
    private static final class Workload {
        final Tailor tailor;
        final Map<LocalDate, Double> booked = new HashMap<>();
        double totalHours;

        Workload(Tailor tailor) {
            this.tailor = tailor;
        }

        double freeOn(LocalDate day, Shop shop) {
            if (!shop.isWorkingDay(day)) return 0.0;
            return Math.max(0.0, tailor.hoursPerDay() - booked.getOrDefault(day, 0.0));
        }

        /**
         * The date this tailor would finish {@code hours} of work, without
         * booking any of it. Returns null when it does not fit the horizon.
         */
        LocalDate simulateFinish(double hours, Shop shop) {
            if (hours <= 0) return shop.from();
            double left = hours;
            LocalDate day = shop.from();
            for (int i = 0; i < HORIZON_DAYS; i++, day = day.plusDays(1)) {
                double free = freeOn(day, shop);
                if (free <= 0) continue;
                left -= free;
                if (left <= 1e-9) return day;
            }
            return null;
        }

        /** The same walk, but booking the capacity as it goes. */
        LocalDate[] book(double hours, Shop shop) {
            double left = hours;
            LocalDate start = null;
            LocalDate day = shop.from();
            for (int i = 0; i < HORIZON_DAYS; i++, day = day.plusDays(1)) {
                double free = freeOn(day, shop);
                if (free <= 0) continue;
                if (start == null) start = day;
                double take = Math.min(free, left);
                booked.merge(day, take, Double::sum);
                left -= take;
                if (left <= 1e-9) {
                    totalHours += hours;
                    return new LocalDate[]{start, day};
                }
            }
            return null;
        }
    }

    private Scheduler() {}

    public static Result plan(List<Order> orders, List<Tailor> tailors, Shop shop) {
        Map<String, Workload> loads = new LinkedHashMap<>();
        for (Tailor t : tailors) {
            loads.put(t.id(), new Workload(t));
        }

        // Earliest due date first; a higher priority number wins a tie, then
        // the longer job (so the big one is not left to the end).
        List<Order> queue = new ArrayList<>(orders);
        queue.sort(Comparator
                .comparing(Order::due, Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(Comparator.comparingInt(Order::priority).reversed())
                .thenComparing(Comparator.comparingDouble(Order::hours).reversed())
                .thenComparing(Order::id));

        List<Assignment> assignments = new ArrayList<>();
        List<Order> unassignable = new ArrayList<>();

        for (Order order : queue) {
            Workload best = null;
            LocalDate bestFinish = null;

            for (Workload load : loads.values()) {
                if (!load.tailor.canDo(order.skill())) continue;
                LocalDate finish = load.simulateFinish(order.hours(), shop);
                if (finish == null) continue;
                // Earliest finish wins; on a tie, spread the work to whoever
                // is carrying less of it.
                if (bestFinish == null
                        || finish.isBefore(bestFinish)
                        || (finish.isEqual(bestFinish) && load.totalHours < best.totalHours)) {
                    best = load;
                    bestFinish = finish;
                }
            }

            if (best == null) {
                unassignable.add(order);
                continue;
            }

            LocalDate[] span = best.book(order.hours(), shop);
            if (span == null) {
                unassignable.add(order);
                continue;
            }
            long daysLate = order.due() == null ? 0
                    : Math.max(0, ChronoUnit.DAYS.between(order.due(), span[1]));
            assignments.add(new Assignment(order, best.tailor, span[0], span[1], daysLate));
        }

        Map<String, Double> hoursByTailor = new LinkedHashMap<>();
        loads.forEach((id, load) -> hoursByTailor.put(id, load.totalHours));
        return new Result(assignments, unassignable, hoursByTailor, shop);
    }

    /** Working days in [from, to], for utilisation percentages. */
    public static long workingDaysBetween(Shop shop, LocalDate to) {
        long count = 0;
        for (LocalDate d = shop.from(); !d.isAfter(to); d = d.plusDays(1)) {
            if (shop.isWorkingDay(d)) count++;
        }
        return count;
    }
}
