package app.anchor.agent;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.provider.Telephony;
import android.telecom.TelecomManager;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Set;
import java.util.TreeSet;

/**
 * Apps that came with the phone. Only the computer removes one, for this phone's user over USB
 * ("pm uninstall --user 0"); this reports what's what, and brings one back when the computer asks.
 */
final class SystemApps {
    private SystemApps() {
    }

    /**
     * System apps with an icon that were removed for this user. Anchored apps are only hidden (still
     * installed), so they're not in this list even though Android's package list leaves them out too.
     */
    static JSONArray removed(Context c) throws JSONException {
        PackageManager pm = c.getPackageManager();
        Set<String> withIcon = new TreeSet<>();
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for (ResolveInfo ri : pm.queryIntentActivities(launcher,
                PackageManager.MATCH_UNINSTALLED_PACKAGES | PackageManager.MATCH_DISABLED_COMPONENTS)) {
            withIcon.add(ri.activityInfo.packageName);
        }
        Set<String> blocked = Core.blocked(c);
        JSONArray out = new JSONArray();
        for (ApplicationInfo ai : pm.getInstalledApplications(PackageManager.MATCH_UNINSTALLED_PACKAGES)) {
            boolean system = (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
            boolean installed = (ai.flags & ApplicationInfo.FLAG_INSTALLED) != 0;
            if (system && !installed && withIcon.contains(ai.packageName) && !blocked.contains(ai.packageName)) {
                out.put(new JSONObject().put("pkg", ai.packageName).put("label", String.valueOf(ai.loadLabel(pm))));
            }
        }
        return out;
    }

    /** Apps the phone can't work without: never offered for removal (Phone, SMS, home screen, Settings, stores). */
    static JSONArray core(Context c) {
        Set<String> out = new TreeSet<>();
        out.add(c.getPackageName());
        out.add("com.android.vending");  // Play Store: the way to get removed apps back
        out.add("com.android.settings");
        PackageManager pm = c.getPackageManager();
        add(out, pm.resolveActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME),
                PackageManager.MATCH_DEFAULT_ONLY));
        add(out, pm.resolveActivity(new Intent(android.provider.Settings.ACTION_SETTINGS), 0));
        try {
            TelecomManager tm = c.getSystemService(TelecomManager.class);
            if (tm != null && tm.getDefaultDialerPackage() != null) out.add(tm.getDefaultDialerPackage());
        } catch (RuntimeException ignored) {
        }
        try {
            String sms = Telephony.Sms.getDefaultSmsPackage(c);
            if (sms != null) out.add(sms);
        } catch (RuntimeException ignored) {
        }
        return new JSONArray(out);
    }

    /** Brings back a system app removed for this user, as it was on a new phone. Needs the computer's key. */
    static void restore(Context c, String pkg) throws JSONException {
        boolean removed = false;
        JSONArray list = removed(c);
        for (int i = 0; i < list.length(); i++) removed |= pkg.equals(list.getJSONObject(i).getString("pkg"));
        if (!removed) throw new IllegalArgumentException(pkg + " isn't a removed system app");
        if (!Core.dpm(c).installExistingPackage(Core.admin(c), pkg)) {
            throw new IllegalArgumentException("Android didn't bring " + pkg + " back");
        }
    }

    private static void add(Set<String> out, ResolveInfo ri) {
        if (ri != null && ri.activityInfo != null) out.add(ri.activityInfo.packageName);
    }

}
