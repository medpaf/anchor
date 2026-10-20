package app.anchor.agent;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * Plain-JDK tests for Timing (no Android needed). Run with tests/run_tests.sh, or:
 *   javac -d /tmp/t android/src/app/anchor/agent/Timing.java android/test/TimingTest.java
 *   java -cp /tmp/t app.anchor.agent.TimingTest
 */
public final class TimingTest {
    private static final ZoneId LISBON = ZoneId.of("Europe/Lisbon");
    private static final int[] EVERY_DAY = {1, 2, 3, 4, 5, 6, 7};
    private static final int[] WEEKDAYS = {1, 2, 3, 4, 5};
    private static int passed;
    private static int failed;

    public static void main(String[] args) {
        overnightWindowCoversBothSidesOfMidnight();
        weekdayWindowSkipsWeekend();
        nextChangeFindsStartAndEnd();
        backToBackWindowsMerge();
        disabledSchedulesAreIgnored();
        fullDayWhenStartEqualsEnd();
        daylightSavingKeepsWallClockTimes();
        overnightFromFridayEndsSaturdayMorning();
        parsesAndFormatsTimes();
        rejectsBadInput();
        System.out.println(passed + " passed, " + failed + " failed");
        if (failed > 0) System.exit(1);
    }

    // 2026-10-19 is a Monday.
    private static long at(String isoLocal) {
        return LocalDateTime.parse(isoLocal).atZone(LISBON).toInstant().toEpochMilli();
    }

    private static Timing.Schedule sched(String name, int[] days, String start, String end) {
        return new Timing.Schedule(name, name, true, days, Timing.parseTime(start), Timing.parseTime(end));
    }

    private static void check(String name, boolean ok) {
        if (ok) passed++;
        else failed++;
        System.out.println((ok ? "PASS " : "FAIL ") + name);
    }

    private static void overnightWindowCoversBothSidesOfMidnight() {
        List<Timing.Schedule> s = Collections.singletonList(sched("Night", EVERY_DAY, "22:30", "07:00"));
        check("night: 21:00 is free", Timing.active(s, at("2026-10-19T21:00"), LISBON) == null);
        Timing.Window w = Timing.active(s, at("2026-10-19T23:15"), LISBON);
        check("night: 23:15 is blocked until 07:00 next day", w != null && w.end == at("2026-10-20T07:00"));
        w = Timing.active(s, at("2026-10-20T03:00"), LISBON);
        check("night: 03:00 is blocked (started yesterday)", w != null && w.end == at("2026-10-20T07:00"));
        check("night: 07:00 exactly is free", Timing.active(s, at("2026-10-20T07:00"), LISBON) == null);
    }

    private static void weekdayWindowSkipsWeekend() {
        List<Timing.Schedule> s = Collections.singletonList(sched("Work", WEEKDAYS, "09:00", "17:00"));
        check("work: Monday 10:00 blocked", Timing.active(s, at("2026-10-19T10:00"), LISBON) != null);
        check("work: Saturday 10:00 free", Timing.active(s, at("2026-10-24T10:00"), LISBON) == null);
        check("work: Friday 16:59 blocked", Timing.active(s, at("2026-10-23T16:59"), LISBON) != null);
        check("work: Friday 17:00 free", Timing.active(s, at("2026-10-23T17:00"), LISBON) == null);
    }

    private static void nextChangeFindsStartAndEnd() {
        List<Timing.Schedule> s = Collections.singletonList(sched("Work", WEEKDAYS, "09:00", "17:00"));
        check("next change before work is 09:00",
                Timing.nextChange(s, at("2026-10-19T08:00"), LISBON) == at("2026-10-19T09:00"));
        check("next change during work is 17:00",
                Timing.nextChange(s, at("2026-10-19T12:00"), LISBON) == at("2026-10-19T17:00"));
        check("next change on Friday evening is Monday 09:00",
                Timing.nextChange(s, at("2026-10-23T18:00"), LISBON) == at("2026-10-26T09:00"));
        check("no schedules, no change", Timing.nextChange(Collections.<Timing.Schedule>emptyList(),
                at("2026-10-19T08:00"), LISBON) == 0);
    }

    private static void backToBackWindowsMerge() {
        List<Timing.Schedule> s = Arrays.asList(
                sched("Work", WEEKDAYS, "09:00", "17:00"), sched("Evening", WEEKDAYS, "17:00", "20:00"));
        Timing.Window w = Timing.active(s, at("2026-10-19T10:00"), LISBON);
        check("back-to-back windows count as one block until 20:00", w != null && w.end == at("2026-10-19T20:00"));
    }

    private static void disabledSchedulesAreIgnored() {
        Timing.Schedule off = new Timing.Schedule("x", "Off", false, EVERY_DAY, 0, 600);
        check("disabled schedule never active",
                Timing.active(Collections.singletonList(off), at("2026-10-19T05:00"), LISBON) == null);
    }

    private static void fullDayWhenStartEqualsEnd() {
        List<Timing.Schedule> s = Collections.singletonList(sched("Sunday", new int[]{7}, "00:00", "00:00"));
        Timing.Window w = Timing.active(s, at("2026-10-25T13:00"), LISBON);
        check("00:00–00:00 on Sunday blocks the whole day", w != null && w.end == at("2026-10-26T00:00"));
        check("…and not Monday", Timing.active(s, at("2026-10-26T13:00"), LISBON) == null);
    }

    private static void daylightSavingKeepsWallClockTimes() {
        // Portugal leaves summer time on 2026-10-25 at 02:00 (clocks go back an hour).
        List<Timing.Schedule> s = Collections.singletonList(sched("Night", EVERY_DAY, "22:30", "07:00"));
        Timing.Window w = Timing.active(s, at("2026-10-25T01:00"), LISBON);
        check("DST night still ends at 07:00 local", w != null && w.end == at("2026-10-25T07:00"));
    }

    private static void overnightFromFridayEndsSaturdayMorning() {
        List<Timing.Schedule> s = Collections.singletonList(sched("Fri night", new int[]{5}, "23:00", "02:00"));
        check("Fri 23:00 window active Sat 01:00", Timing.active(s, at("2026-10-24T01:00"), LISBON) != null);
        check("…but not Sun 01:00", Timing.active(s, at("2026-10-25T01:00"), LISBON) == null);
    }

    private static void parsesAndFormatsTimes() {
        check("parse 07:05", Timing.parseTime("07:05") == 425);
        check("format 425", Timing.formatTime(425).equals("07:05"));
    }

    private static void rejectsBadInput() {
        String[] bad = {"24:00", "7", "12:60", "-1:00"};
        for (String b : bad) {
            boolean threw = false;
            try {
                Timing.parseTime(b);
            } catch (IllegalArgumentException e) {
                threw = true;
            }
            check("rejects time " + b, threw);
        }
        boolean threw = false;
        try {
            new Timing.Schedule("x", "x", true, new int[]{0}, 0, 60);
        } catch (IllegalArgumentException e) {
            threw = true;
        }
        check("rejects day 0", threw);
    }
}
