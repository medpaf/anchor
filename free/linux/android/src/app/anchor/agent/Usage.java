package app.anchor.agent;

import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.os.Process;

import java.util.Calendar;

/**
 * How long an app was on screen, for the details screens (phone and computer). Read from Android's
 * own usage records on the phone; nothing leaves the phone except through the USB cable.
 *
 * <p>Needs the "usage access" app op, which the computer turns on over USB (Agent.allow_background).
 */
final class Usage {
    private Usage() {
    }

    static boolean allowed(Context c) {
        AppOpsManager ops = (AppOpsManager) c.getSystemService(Context.APP_OPS_SERVICE);
        return ops != null && ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(),
                c.getPackageName()) == AppOpsManager.MODE_ALLOWED;
    }

    /** Midnight today, or that many days before it. */
    static long midnight(int daysAgo) {
        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        cal.add(Calendar.DAY_OF_YEAR, -daysAgo);
        return cal.getTimeInMillis();
    }

    /** Milliseconds the app was in the foreground between begin and end. */
    static long foreground(Context c, String pkg, long begin, long end) {
        UsageStatsManager usm = (UsageStatsManager) c.getSystemService(Context.USAGE_STATS_SERVICE);
        if (usm == null) return 0;
        UsageEvents events = usm.queryEvents(begin, end);
        UsageEvents.Event e = new UsageEvents.Event();
        long total = 0;
        long start = -1;
        boolean seen = false;
        while (events.hasNextEvent()) {
            events.getNextEvent(e);
            if (!pkg.equals(e.getPackageName())) continue;
            int type = e.getEventType();
            if (type == UsageEvents.Event.ACTIVITY_RESUMED) {
                if (start < 0) start = e.getTimeStamp();
            } else if (type == UsageEvents.Event.ACTIVITY_PAUSED || type == UsageEvents.Event.ACTIVITY_STOPPED) {
                if (start >= 0) {
                    total += e.getTimeStamp() - start;
                    start = -1;
                } else if (!seen) {
                    total += e.getTimeStamp() - begin;  // it was already open when the period began
                }
            }
            seen = true;
        }
        if (start >= 0) total += end - start;  // still open now
        return Math.max(0, total);
    }
}
