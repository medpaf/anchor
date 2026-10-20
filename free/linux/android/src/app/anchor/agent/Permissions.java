package app.anchor.agent;

import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.PermissionInfo;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

final class Permissions {
    private static final String PREFS = "anchor_permissions";
    private static final String KEY_REVOKED_APPS = "revoked_apps";

    private Permissions() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static void record(Context c, Collection<String> blocked) {
        for (String pkg : revokedApps(c)) {
            if (!blocked.contains(pkg) && prefs(c).contains(pkg)) restore(c, pkg);
        }
        prefs(c).edit().putStringSet(KEY_REVOKED_APPS, new TreeSet<>(blocked)).commit();
    }

    static Set<String> revokedApps(Context c) {
        return new TreeSet<>(prefs(c).getStringSet(KEY_REVOKED_APPS, Collections.<String>emptySet()));
    }

    static Map<String, Integer> counts(Context c) {
        Map<String, Integer> out = new TreeMap<>();
        for (String pkg : revokedApps(c)) {
            int n = prefs(c).getStringSet(pkg, Collections.<String>emptySet()).size();
            if (n > 0) out.put(pkg, n);
        }
        return out;
    }

    static void revoke(Context c, String pkg) {
        DevicePolicyManager dpm = Core.dpm(c);
        ComponentName admin = Core.admin(c);
        PackageManager pm = c.getPackageManager();
        Set<String> granted = new TreeSet<>(prefs(c).getStringSet(pkg, Collections.<String>emptySet()));
        boolean changed = false;
        for (String perm : runtimePermissions(c, pkg)) {
            if (dpm.getPermissionGrantState(admin, pkg, perm) == DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED) {
                continue;
            }
            if (pm.checkPermission(perm, pkg) == PackageManager.PERMISSION_GRANTED && granted.add(perm)) {
                changed = true;
            }
            try {
                dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED);
            } catch (RuntimeException ignored) {

            }
        }
        if (changed) prefs(c).edit().putStringSet(pkg, granted).commit();
    }

    static void restore(Context c, String pkg) {
        DevicePolicyManager dpm = Core.dpm(c);
        ComponentName admin = Core.admin(c);
        Set<String> granted = prefs(c).getStringSet(pkg, Collections.<String>emptySet());
        for (String perm : runtimePermissions(c, pkg)) {
            try {

                if (granted.contains(perm)) {
                    dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED);
                }
                dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT);
            } catch (RuntimeException ignored) {
            }
        }
        prefs(c).edit().remove(pkg).commit();
    }

    static org.json.JSONObject info(Context c, String pkg) throws org.json.JSONException {
        PackageManager pm = c.getPackageManager();
        PackageInfo p;
        try {
            p = pm.getPackageInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES);
        } catch (PackageManager.NameNotFoundException e) {
            throw new IllegalArgumentException(pkg + " isn't installed");
        }
        DevicePolicyManager dpm = Core.dpm(c);
        ComponentName admin = Core.admin(c);
        boolean blocked = Core.blocked(c).contains(pkg);
        org.json.JSONArray perms = new org.json.JSONArray();
        for (String perm : runtimePermissions(c, pkg)) {
            String label = perm;
            try {
                CharSequence l = pm.getPermissionInfo(perm, 0).loadLabel(pm);
                if (l != null) label = l.toString();
            } catch (PackageManager.NameNotFoundException ignored) {
            }
            perms.put(new org.json.JSONObject()
                    .put("name", perm)
                    .put("label", label)
                    .put("granted", pm.checkPermission(perm, pkg) == PackageManager.PERMISSION_GRANTED)
                    .put("locked", dpm.getPermissionGrantState(admin, pkg, perm)
                            != DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT)
                    .put("had", prefs(c).getStringSet(pkg, Collections.<String>emptySet()).contains(perm)));
        }
        org.json.JSONObject out = new org.json.JSONObject();
        if (Usage.allowed(c)) {
            long now = System.currentTimeMillis();
            out.put("usage_today", Usage.foreground(c, pkg, Usage.midnight(0), now));
            out.put("usage_week", Usage.foreground(c, pkg, Usage.midnight(6), now));
        }
        return out
                .put("pkg", pkg)
                .put("label", String.valueOf(p.applicationInfo.loadLabel(pm)))
                .put("version", p.versionName == null ? "" : p.versionName)
                .put("version_code", p.getLongVersionCode())
                .put("installed", p.firstInstallTime)
                .put("updated", p.lastUpdateTime)
                .put("system", (p.applicationInfo.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0)
                .put("target_sdk", p.applicationInfo.targetSdkVersion)
                .put("blocked", blocked)
                .put("permissions", perms);
    }

    static void set(Context c, String pkg, String perm, boolean grant) {
        if (!runtimePermissions(c, pkg).contains(perm)) {
            throw new IllegalArgumentException(pkg + " doesn't use " + perm);
        }
        if (Core.blocked(c).contains(pkg)) {
            throw new IllegalArgumentException("Its permissions are removed while it's blocked. Release it first.");
        }
        DevicePolicyManager dpm = Core.dpm(c);
        ComponentName admin = Core.admin(c);
        boolean ok = dpm.setPermissionGrantState(admin, pkg, perm, grant
                ? DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED
                : DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED);
        dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT);
        if (!ok) throw new IllegalArgumentException("Android didn't allow changing this permission");
    }

    static List<String> runtimePermissions(Context c, String pkg) {
        List<String> out = new ArrayList<>();
        PackageManager pm = c.getPackageManager();
        PackageInfo info;
        try {
            info = pm.getPackageInfo(pkg, PackageManager.GET_PERMISSIONS | PackageManager.MATCH_UNINSTALLED_PACKAGES);
        } catch (PackageManager.NameNotFoundException e) {
            return out;
        }
        if (info.requestedPermissions == null) return out;
        for (String perm : info.requestedPermissions) {
            try {
                PermissionInfo pi = pm.getPermissionInfo(perm, 0);
                if (pi.getProtection() == PermissionInfo.PROTECTION_DANGEROUS) out.add(perm);
            } catch (PackageManager.NameNotFoundException ignored) {

            }
        }
        return out;
    }
}
