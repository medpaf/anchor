package app.anchor.agent;

import android.Manifest;
import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.admin.DevicePolicyManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.regex.Pattern;

final class InstallBlocks {
    static final String ACTION_CHECK = "app.anchor.agent.CHECK_INSTALLS";
    private static final String PREFS = "anchor";
    private static final String KEY_LIST = "install_blocks";
    private static final String KEY_SET = "install_blocks_set";
    private static final String KEY_KEPT = "install_kept";
    private static final String KEY_CAUGHT = "install_caught";
    private static final String KEY_PLACEHOLDERS = "install_placeholders";
    static final String PLACEHOLDER_META = "app.anchor.placeholder";
    private static final String CHANNEL = "blocked";
    private static final long CHECK_EVERY_MS = 60_000;
    private static final Pattern PACKAGE = Pattern.compile("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+");

    private InstallBlocks() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static JSONArray list(Context c) {
        try {
            return new JSONArray(prefs(c).getString(KEY_LIST, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    static Map<String, String> names(Context c) {
        Map<String, String> out = new TreeMap<>();
        JSONArray a = list(c);
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o != null) out.put(o.optString("pkg"), o.optString("name", o.optString("pkg")));
        }
        return out;
    }

    static boolean isSet(Context c) {
        return prefs(c).getBoolean(KEY_SET, false);
    }

    static Set<String> kept(Context c) {
        return new TreeSet<>(prefs(c).getStringSet(KEY_KEPT, Collections.<String>emptySet()));
    }

    static void set(Context c, JSONArray apps) throws JSONException {
        Map<String, String> next = new TreeMap<>();
        for (int i = 0; i < apps.length(); i++) {
            JSONObject o = apps.getJSONObject(i);
            String pkg = o.getString("pkg").trim();
            if (!PACKAGE.matcher(pkg).matches()) throw new IllegalArgumentException("Not a package name: " + pkg);
            if (pkg.equals(c.getPackageName())) continue;
            next.put(pkg, o.optString("name", pkg));
        }
        Set<String> before = names(c).keySet();
        Set<String> kept = kept(c);
        for (String pkg : next.keySet()) {
            if (!before.contains(pkg) && Core.isInstalled(c, pkg) && !isPlaceholder(c, pkg)) kept.add(pkg);
        }
        kept.retainAll(next.keySet());
        JSONArray out = new JSONArray();
        for (Map.Entry<String, String> e : next.entrySet()) {
            out.put(new JSONObject().put("pkg", e.getKey()).put("name", e.getValue()));
        }
        prefs(c).edit().putString(KEY_LIST, out.toString()).putBoolean(KEY_SET, true)
                .putStringSet(KEY_KEPT, kept).commit();
    }

    static boolean isPlaceholder(Context c, String pkg) {
        try {
            ApplicationInfo ai = c.getPackageManager().getApplicationInfo(pkg,
                    PackageManager.GET_META_DATA | PackageManager.MATCH_UNINSTALLED_PACKAGES);
            return (ai.flags & ApplicationInfo.FLAG_INSTALLED) != 0
                    && ai.metaData != null && ai.metaData.containsKey(PLACEHOLDER_META);
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    static Set<String> placeholders(Context c) {
        Set<String> out = new TreeSet<>();
        for (String pkg : names(c).keySet()) if (isPlaceholder(c, pkg)) out.add(pkg);
        return out;
    }

    static Set<String> missing(Context c) {
        Set<String> out = new TreeSet<>();
        for (String pkg : names(c).keySet()) if (!Core.isInstalled(c, pkg)) out.add(pkg);
        return out;
    }

    static Set<String> syncPlaceholders(Context c) {
        Set<String> current = placeholders(c);
        Set<String> known = new TreeSet<>(prefs(c).getStringSet(KEY_PLACEHOLDERS, Collections.<String>emptySet()));
        Set<String> names = names(c).keySet();
        for (String pkg : known) {
            if (!names.contains(pkg) && isPlaceholder(c, pkg)) uninstall(c, pkg);
        }
        prefs(c).edit().putStringSet(KEY_PLACEHOLDERS, current).commit();
        return current;
    }

    static void uninstall(Context c, String pkg) {
        DevicePolicyManager dpm = Core.dpm(c);
        try {
            dpm.setUninstallBlocked(Core.admin(c), pkg, false);
            dpm.setApplicationHidden(Core.admin(c), pkg, false);
        } catch (RuntimeException ignored) {
        }
        int flags = PendingIntent.FLAG_UPDATE_CURRENT
                | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        PendingIntent done = PendingIntent.getBroadcast(c, pkg.hashCode(),
                new Intent(c, AlarmReceiver.class).setAction(ACTION_CHECK), flags);
        c.getPackageManager().getPackageInstaller().uninstall(pkg, done.getIntentSender());
    }

    static void uninstallCaught(Context c, String pkg) {
        if (!caught(c).contains(pkg)) throw new IllegalArgumentException(pkg + " isn't a blocked app that's installed");
        uninstall(c, pkg);
    }

    static void clear(Context c) {
        for (String pkg : placeholders(c)) uninstall(c, pkg);
        prefs(c).edit().putString(KEY_LIST, "[]").putStringSet(KEY_KEPT, Collections.<String>emptySet())
                .putStringSet(KEY_CAUGHT, Collections.<String>emptySet())
                .putStringSet(KEY_PLACEHOLDERS, Collections.<String>emptySet()).commit();
    }

    static Set<String> caught(Context c) {
        Set<String> kept = kept(c);
        Set<String> out = new TreeSet<>();
        boolean changed = false;
        for (String pkg : names(c).keySet()) {
            boolean installed = Core.isInstalled(c, pkg);
            if (installed && !kept.contains(pkg) && !isPlaceholder(c, pkg)) out.add(pkg);
            if (!installed && kept.remove(pkg)) changed = true;
        }
        if (changed) prefs(c).edit().putStringSet(KEY_KEPT, kept).commit();
        return out;
    }

    static void check(Context c) {
        if (!Core.isOwner(c)) return;
        if (Core.needsApply(c)) Core.apply(c);
        else watch(c);
    }

    static void applied(Context c, Set<String> caughtAndHidden) {
        Set<String> before = new TreeSet<>(prefs(c).getStringSet(KEY_CAUGHT, Collections.<String>emptySet()));
        Set<String> fresh = new TreeSet<>(caughtAndHidden);
        fresh.removeAll(before);
        prefs(c).edit().putStringSet(KEY_CAUGHT, new TreeSet<>(caughtAndHidden)).commit();
        Map<String, String> names = names(c);
        for (String pkg : fresh) notifyBlocked(c, pkg, names.containsKey(pkg) ? names.get(pkg) : pkg);
        watch(c);
    }

    static void watch(Context c) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        PendingIntent pi = PendingIntent.getBroadcast(c, 1,
                new Intent(c, AlarmReceiver.class).setAction(ACTION_CHECK),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        am.cancel(pi);
        if (!Core.watchInstalls(c)) return;
        long at = System.currentTimeMillis() + CHECK_EVERY_MS;
        if (Core.canWakeExactly(c)) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
        else am.setWindow(AlarmManager.RTC_WAKEUP, at, CHECK_EVERY_MS, pi);
    }

    private static void notifyBlocked(Context c, String pkg, String name) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 33) {

            try {
                Core.dpm(c).setPermissionGrantState(Core.admin(c), c.getPackageName(),
                        Manifest.permission.POST_NOTIFICATIONS, DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED);
            } catch (RuntimeException ignored) {
            }
        }
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Blocked apps",
                NotificationManager.IMPORTANCE_DEFAULT));
        PendingIntent open = PendingIntent.getActivity(c, 0, new Intent(c, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
        Notification n = new Notification.Builder(c, CHANNEL)
                .setSmallIcon(R_drawable(c, "ic_stat"))
                .setColor(0xFF7C3AED)
                .setContentTitle(name + " is blocked")
                .setContentText("It's on your 'Never allow' list. Release it in Anchor on your computer to use it.")
                .setStyle(new Notification.BigTextStyle().bigText(
                        "It's on your 'Never allow' list, so Anchor hid it. Nothing was deleted. "
                                + "Release it in Anchor on your computer to use it."))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build();
        nm.notify(pkg.hashCode(), n);
    }

    private static int R_drawable(Context c, String name) {
        int id = c.getResources().getIdentifier(name, "drawable", c.getPackageName());
        return id != 0 ? id : android.R.drawable.ic_lock_lock;
    }
}
