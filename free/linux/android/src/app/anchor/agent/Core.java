package app.anchor.agent;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.UserManager;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

final class Core {
    private static final String PREFS = "anchor";
    private static final String KEY_TOKEN_HASH = "token_hash";
    private static final String KEY_SELECTED = "selected";
    private static final String KEY_BLOCKED = "blocked";
    private static final String KEY_FAILED = "failed";
    private static final String KEY_SHIFTED = "shifted";
    private static final String KEY_SHIFTED_AT = "shifted_at";
    private static final String KEY_UNTIL = "until";
    private static final String KEY_PAUSED = "paused";
    private static final String KEY_SCHEDULES = "schedules";

    private static final String[] RESTRICTIONS = {
            UserManager.DISALLOW_ADD_USER,
            UserManager.DISALLOW_USER_SWITCH,
    };

    private Core() {
    }

    static ComponentName admin(Context c) {
        return new ComponentName(c, AdminReceiver.class);
    }

    static DevicePolicyManager dpm(Context c) {
        return c.getSystemService(DevicePolicyManager.class);
    }

    static boolean isOwner(Context c) {
        return dpm(c).isDeviceOwnerApp(c.getPackageName());
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static Set<String> getSet(Context c, String key) {
        return new TreeSet<>(prefs(c).getStringSet(key, Collections.<String>emptySet()));
    }

    private static void putSet(Context c, String key, Collection<String> value) {
        prefs(c).edit().putStringSet(key, new TreeSet<>(value)).commit();
    }

    static Set<String> selected(Context c) {
        return getSet(c, KEY_SELECTED);
    }

    static Set<String> blocked(Context c) {
        return getSet(c, KEY_BLOCKED);
    }

    static Set<String> failed(Context c) {
        return getSet(c, KEY_FAILED);
    }

    static boolean isShifted(Context c) {
        long now = System.currentTimeMillis();
        return mode(c, now) != null || !scheduledNow(c, now).isEmpty();
    }

    static String mode(Context c, long now) {
        if (prefs(c).getBoolean(KEY_SHIFTED, false)) return "manual";
        if (timerUntil(c) > now) return "timer";
        return null;
    }

    static long timerUntil(Context c) {
        return prefs(c).getLong(KEY_UNTIL, 0);
    }

    static long shiftEnds(Context c, long now) {
        return "timer".equals(mode(c, now)) ? timerUntil(c) : 0;
    }

    static Map<String, Long> paused(Context c, long now) {
        Map<String, Long> out = new TreeMap<>();
        try {
            JSONObject o = new JSONObject(prefs(c).getString(KEY_PAUSED, "{}"));
            for (Iterator<String> it = o.keys(); it.hasNext(); ) {
                String id = it.next();
                long until = o.getLong(id);
                if (until > now) out.put(id, until);
            }
        } catch (JSONException ignored) {
        }
        return out;
    }

    static Map<String, Long> scheduledNow(Context c, long now) {
        Map<String, Long> out = new TreeMap<>();
        Map<String, Long> paused = paused(c, now);
        for (Timing.Schedule s : schedules(c)) {
            if (!s.enabled || paused.containsKey(s.id)) continue;
            Timing.Window w = Timing.active(Collections.singletonList(s), now, ZoneId.systemDefault());
            if (w == null) continue;
            for (String p : s.packages) {
                Long prev = out.get(p);
                out.put(p, prev == null ? w.end : Math.max(prev, w.end));
            }
        }
        return out;
    }

    static long shiftedAt(Context c) {
        return prefs(c).getLong(KEY_SHIFTED_AT, 0);
    }

    static boolean isPaired(Context c) {
        return prefs(c).getString(KEY_TOKEN_HASH, null) != null;
    }

    static boolean checkToken(Context c, String token) {
        String stored = prefs(c).getString(KEY_TOKEN_HASH, null);
        if (stored == null || token == null || token.isEmpty()) return false;
        return MessageDigest.isEqual(
                stored.getBytes(StandardCharsets.US_ASCII),
                sha256(token).getBytes(StandardCharsets.US_ASCII));
    }

    static void pair(Context c, String token) {
        prefs(c).edit().putString(KEY_TOKEN_HASH, sha256(token)).commit();
    }

    static void unpair(Context c) {
        prefs(c).edit().clear().commit();
    }

    private static String sha256(String s) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : d) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    static void setSelected(Context c, Collection<String> packages) {
        Set<String> clean = new TreeSet<>(packages);
        clean.remove(c.getPackageName());
        putSet(c, KEY_SELECTED, clean);
    }

    static void setShifted(Context c, boolean shifted) {
        if (!shifted) {
            unshift(c);
            return;
        }
        prefs(c).edit().putBoolean(KEY_SHIFTED, true).putLong(KEY_UNTIL, 0)
                .putLong(KEY_SHIFTED_AT, System.currentTimeMillis()).commit();
    }

    static void shiftFor(Context c, int minutes) {
        if (minutes < 1 || minutes > 7 * 24 * 60) throw new IllegalArgumentException("You can anchor for 1 minute to 7 days");
        long now = System.currentTimeMillis();
        prefs(c).edit().putBoolean(KEY_SHIFTED, false).putLong(KEY_UNTIL, now + minutes * 60_000L)
                .putLong(KEY_SHIFTED_AT, now).commit();
    }

    static void endShift(Context c) {
        prefs(c).edit().putBoolean(KEY_SHIFTED, false).putLong(KEY_UNTIL, 0).putLong(KEY_SHIFTED_AT, 0)
                .putStringSet(KEY_SELECTED, Collections.<String>emptySet()).commit();
    }

    private static void expireTimer(Context c, long now) {
        long until = timerUntil(c);
        if (until > 0 && until <= now && !prefs(c).getBoolean(KEY_SHIFTED, false)) endShift(c);
    }

    static void unshift(Context c) {
        long now = System.currentTimeMillis();
        Map<String, Long> paused = paused(c, now);
        for (Timing.Schedule s : schedules(c)) {
            if (!s.enabled) continue;
            Timing.Window w = Timing.active(Collections.singletonList(s), now, ZoneId.systemDefault());
            if (w != null) paused.put(s.id, w.end);
        }
        prefs(c).edit().putBoolean(KEY_SHIFTED, false).putLong(KEY_UNTIL, 0)
                .putString(KEY_PAUSED, new JSONObject(paused).toString()).putLong(KEY_SHIFTED_AT, 0)
                .putStringSet(KEY_SELECTED, Collections.<String>emptySet()).commit();
    }

    static List<Timing.Schedule> schedules(Context c) {
        try {
            return parseSchedules(new JSONArray(prefs(c).getString(KEY_SCHEDULES, "[]")));
        } catch (JSONException e) {
            return new ArrayList<>();
        }
    }

    static JSONArray schedulesJson(Context c) {
        try {
            return new JSONArray(prefs(c).getString(KEY_SCHEDULES, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    static void setSchedules(Context c, JSONArray json) throws JSONException {
        parseSchedules(json);
        prefs(c).edit().putString(KEY_SCHEDULES, json.toString()).commit();
    }

    static void addSchedule(Context c, String pkg, String name, int[] days, String start, String end)
            throws JSONException {
        JSONObject o = new JSONObject();
        o.put("id", java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 8));
        o.put("name", name);
        o.put("enabled", true);
        JSONArray d = new JSONArray();
        for (int day : days) d.put(day);
        o.put("days", d);
        o.put("start", start);
        o.put("end", end);
        o.put("packages", new JSONArray().put(pkg));
        JSONArray all = schedulesJson(c);
        all.put(o);
        setSchedules(c, all);
    }

    static List<Timing.Schedule> parseSchedules(JSONArray json) throws JSONException {
        List<Timing.Schedule> out = new ArrayList<>();
        for (int i = 0; i < json.length(); i++) {
            JSONObject o = json.getJSONObject(i);
            JSONArray d = o.getJSONArray("days");
            int[] days = new int[d.length()];
            for (int j = 0; j < days.length; j++) days[j] = d.getInt(j);
            if (days.length == 0) throw new IllegalArgumentException("A schedule needs at least one day");
            List<String> packages = new ArrayList<>();
            JSONArray p = o.optJSONArray("packages");
            if (p != null) for (int j = 0; j < p.length(); j++) packages.add(p.getString(j));
            out.add(new Timing.Schedule(o.getString("id"), o.optString("name", "Schedule"),
                    o.optBoolean("enabled", true), days,
                    Timing.parseTime(o.getString("start")), Timing.parseTime(o.getString("end")), packages));
        }
        return out;
    }

    private static boolean anyEnabled(List<Timing.Schedule> schedules) {
        for (Timing.Schedule s : schedules) if (s.enabled && !s.packages.isEmpty()) return true;
        return false;
    }

    static synchronized List<String> apply(Context c) {
        DevicePolicyManager dpm = dpm(c);
        ComponentName admin = admin(c);
        long now = System.currentTimeMillis();
        PrivateDns.reapply(c);
        expireTimer(c, now);
        List<Timing.Schedule> schedules = schedules(c);

        Set<String> caught = InstallBlocks.caught(c);
        Set<String> want = wanted(c, now, caught);
        want.addAll(InstallBlocks.syncPlaceholders(c));
        boolean shifted = !want.isEmpty() || mode(c, now) != null;

        boolean lockdown = shifted || !InstallBlocks.names(c).isEmpty();
        Set<String> have = blocked(c);

        List<String> release = new ArrayList<>();
        for (String p : have) {
            if (!want.contains(p)) release.add(p);
        }
        if (!release.isEmpty()) {
            for (String p : release) {
                try {
                    dpm.setApplicationHidden(admin, p, false);
                } catch (RuntimeException ignored) {
                }
            }
            dpm.setPackagesSuspended(admin, release.toArray(new String[0]), false);
            for (String p : release) {
                try {
                    dpm.setUninstallBlocked(admin, p, false);
                } catch (RuntimeException ignored) {
                }

                Permissions.restore(c, p);
            }
        }

        List<String> failed = new ArrayList<>();
        if (!want.isEmpty()) {
            String[] refused = dpm.setPackagesSuspended(admin, want.toArray(new String[0]), true);
            if (refused != null) failed.addAll(Arrays.asList(refused));
        }
        Set<String> nowBlocked = new TreeSet<>(want);
        nowBlocked.removeAll(failed);
        for (String p : nowBlocked) {
            try {
                dpm.setUninstallBlocked(admin, p, true);
            } catch (RuntimeException ignored) {
            }

            if (!have.contains(p)) Permissions.revoke(c, p);

            try {
                dpm.setApplicationHidden(admin, p, true);
            } catch (RuntimeException ignored) {
            }
        }

        dpm.setShortSupportMessage(admin, shifted
                ? "Blocked by Anchor. To release it, connect this phone to your computer."
                : null);

        for (String r : RESTRICTIONS) {
            if (lockdown) dpm.addUserRestriction(admin, r);
            else dpm.clearUserRestriction(admin, r);
        }

        putSet(c, KEY_BLOCKED, nowBlocked);

        Permissions.record(c, nowBlocked);
        putSet(c, KEY_FAILED, failed);

        lockClock(c, timerUntil(c) > now || anyEnabled(schedules));
        scheduleWakeUp(c, now, schedules);
        Set<String> caughtHidden = new TreeSet<>(caught);
        caughtHidden.retainAll(nowBlocked);
        InstallBlocks.applied(c, caughtHidden);

        if (shifted || anyEnabled(schedules)) ReapplyJob.schedule(c);
        else ReapplyJob.cancel(c);
        return failed;
    }

    private static void lockClock(Context c, boolean lock) {
        DevicePolicyManager dpm = dpm(c);
        ComponentName admin = admin(c);
        try {
            if (lock) {
                dpm.addUserRestriction(admin, UserManager.DISALLOW_CONFIG_DATE_TIME);
                if (Build.VERSION.SDK_INT >= 30) {
                    dpm.setAutoTimeEnabled(admin, true);
                    dpm.setAutoTimeZoneEnabled(admin, true);
                } else {
                    dpm.setAutoTimeRequired(admin, true);
                }
            } else {
                dpm.clearUserRestriction(admin, UserManager.DISALLOW_CONFIG_DATE_TIME);
                if (Build.VERSION.SDK_INT < 30) dpm.setAutoTimeRequired(admin, false);
            }
        } catch (RuntimeException ignored) {

        }
    }

    private static void scheduleWakeUp(Context c, long now, List<Timing.Schedule> schedules) {
        long next = 0;
        List<Long> times = new ArrayList<>(paused(c, now).values());
        times.add(timerUntil(c));
        times.add(Timing.nextChange(schedules, now, ZoneId.systemDefault()));
        for (long t : times) {
            if (t > now && (next == 0 || t < next)) next = t;
        }
        AlarmManager am = c.getSystemService(AlarmManager.class);
        PendingIntent pi = PendingIntent.getBroadcast(c, 0, new Intent(c, AlarmReceiver.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        am.cancel(pi);
        if (next == 0) return;
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next, pi);
        } else {
            am.setWindow(AlarmManager.RTC_WAKEUP, next, 60_000, pi);
        }
    }

    static boolean canWakeExactly(Context c) {
        return Build.VERSION.SDK_INT < 31 || c.getSystemService(AlarmManager.class).canScheduleExactAlarms();
    }

    static Set<String> wanted(Context c, long now, Set<String> caught) {
        Set<String> candidates = new TreeSet<>(scheduledNow(c, now).keySet());
        candidates.addAll(caught);
        if (mode(c, now) != null) candidates.addAll(selected(c));
        candidates.remove(c.getPackageName());
        Set<String> want = new TreeSet<>();
        for (String p : candidates) {
            if (isInstalled(c, p)) want.add(p);
        }
        return want;
    }

    static boolean needsApply(Context c) {
        Set<String> want = wanted(c, System.currentTimeMillis(), InstallBlocks.caught(c));
        want.addAll(InstallBlocks.placeholders(c));
        Set<String> have = blocked(c);
        have.removeAll(failed(c));
        want.removeAll(failed(c));
        return !want.equals(have);
    }

    static boolean watchInstalls(Context c) {
        long now = System.currentTimeMillis();
        return mode(c, now) != null || anyEnabled(schedules(c)) || !InstallBlocks.names(c).isEmpty();
    }

    static void lockFactoryReset(Context c, boolean lock) {
        if (lock) dpm(c).addUserRestriction(admin(c), UserManager.DISALLOW_FACTORY_RESET);
        else dpm(c).clearUserRestriction(admin(c), UserManager.DISALLOW_FACTORY_RESET);
    }

    static boolean factoryResetLocked(Context c) {
        UserManager um = c.getSystemService(UserManager.class);
        return um != null && um.hasUserRestriction(UserManager.DISALLOW_FACTORY_RESET);
    }

    static void release(Context c) {
        prefs(c).edit().putString(KEY_SCHEDULES, "[]").putString(KEY_PAUSED, "{}").commit();
        InstallBlocks.clear(c);
        unshift(c);
        apply(c);
        lockClock(c, false);
        PrivateDns.release(c);
        try {
            lockFactoryReset(c, false);
        } catch (RuntimeException ignored) {
        }
        unpair(c);
        dpm(c).clearDeviceOwnerApp(c.getPackageName());
    }

    static void uninstallApp(Context c, String pkg) {
        if (pkg.equals(c.getPackageName())) throw new IllegalArgumentException("Anchor can't uninstall itself this way");
        ApplicationInfo ai;
        try {
            ai = c.getPackageManager().getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES);
        } catch (PackageManager.NameNotFoundException e) {
            throw new IllegalArgumentException(pkg + " isn't installed");
        }
        if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) {
            throw new IllegalArgumentException("System apps can't be uninstalled");
        }
        if (InstallBlocks.isPlaceholder(c, pkg)) throw new IllegalArgumentException("That's Anchor's placeholder");
        InstallBlocks.uninstall(c, pkg);
    }

    static boolean isInstalled(Context c, String pkg) {
        try {

            ApplicationInfo ai = c.getPackageManager()
                    .getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES);
            return (ai.flags & ApplicationInfo.FLAG_INSTALLED) != 0;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }
}
