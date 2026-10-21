package app.anchor.agent;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

final class Timing {
    private Timing() {
    }

    static final class Schedule {
        final String id;
        final String name;
        final boolean enabled;

        final boolean[] days = new boolean[8];

        final int start;
        final int end;

        final Set<String> packages;

        Schedule(String id, String name, boolean enabled, int[] isoDays, int start, int end) {
            this(id, name, enabled, isoDays, start, end, Collections.<String>emptySet());
        }

        Schedule(String id, String name, boolean enabled, int[] isoDays, int start, int end,
                 Collection<String> packages) {
            if (start < 0 || start >= 1440 || end < 0 || end >= 1440) {
                throw new IllegalArgumentException("Times must be between 00:00 and 23:59");
            }
            this.id = id;
            this.name = name;
            this.enabled = enabled;
            for (int d : isoDays) {
                if (d < 1 || d > 7) throw new IllegalArgumentException("Days must be 1 (Mon) to 7 (Sun)");
                days[d] = true;
            }
            this.start = start;
            this.end = end;
            this.packages = Collections.unmodifiableSet(new TreeSet<>(packages));
        }

        int lengthMinutes() {
            return end > start ? end - start : end + 1440 - start;
        }
    }

    static final class Window {
        final Schedule schedule;
        final long start;
        final long end;

        Window(Schedule schedule, long start, long end) {
            this.schedule = schedule;
            this.start = start;
            this.end = end;
        }
    }

    static int parseTime(String hhmm) {
        String[] p = hhmm.trim().split(":");
        if (p.length != 2) throw new IllegalArgumentException("Time must look like 22:30: " + hhmm);
        int h = Integer.parseInt(p[0]);
        int m = Integer.parseInt(p[1]);
        if (h < 0 || h > 23 || m < 0 || m > 59) throw new IllegalArgumentException("Bad time: " + hhmm);
        return h * 60 + m;
    }

    static String formatTime(int minutes) {
        return String.format("%02d:%02d", minutes / 60, minutes % 60);
    }

    static List<Window> windows(List<Schedule> schedules, long now, ZoneId zone) {
        List<Window> out = new ArrayList<>();
        LocalDate today = Instant.ofEpochMilli(now).atZone(zone).toLocalDate();
        for (int offset = -1; offset <= 8; offset++) {
            LocalDate date = today.plusDays(offset);
            DayOfWeek dow = date.getDayOfWeek();
            for (Schedule s : schedules) {
                if (!s.enabled || !s.days[dow.getValue()]) continue;

                LocalDate endDate = s.end > s.start ? date : date.plusDays(1);
                ZonedDateTime begin = date.atTime(s.start / 60, s.start % 60).atZone(zone);
                ZonedDateTime finish = endDate.atTime(s.end / 60, s.end % 60).atZone(zone);
                out.add(new Window(s, begin.toInstant().toEpochMilli(), finish.toInstant().toEpochMilli()));
            }
        }
        return out;
    }

    static Window active(List<Schedule> schedules, long now, ZoneId zone) {
        List<Window> all = windows(schedules, now, zone);
        Window best = null;
        for (Window w : all) {
            if (w.start <= now && now < w.end && (best == null || w.end > best.end)) best = w;
        }
        if (best == null) return null;
        long end = best.end;
        boolean extended = true;
        while (extended) {
            extended = false;
            for (Window w : all) {
                if (w.start <= end && w.end > end) {
                    end = w.end;
                    extended = true;
                }
            }
        }
        return new Window(best.schedule, best.start, end);
    }

    static long nextChange(List<Schedule> schedules, long now, ZoneId zone) {
        long next = 0;
        for (Window w : windows(schedules, now, zone)) {
            for (long t : new long[]{w.start, w.end}) {
                if (t > now && (next == 0 || t < next)) next = t;
            }
        }
        return next;
    }
}
