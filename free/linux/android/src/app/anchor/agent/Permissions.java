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

/**
 * Takes away a blocked app's permissions (camera, microphone, location, contacts, photos,
 * notifications… every permission the user grants in a popup) and gives back exactly the ones it
 * had when it's released.
 *
 * <p>Revoked permissions are set to "denied by policy", so they can't be switched back on in
 * Settings while the app is blocked. The permissions an app had before are remembered per app.
 */
final class Permissions {
    private static final String PREFS = "anchor_permissions";
    private static final String KEY_REVOKED_APPS = "revoked_apps";

    private Permissions() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /**
     * Remembers which apps are blocked, restoring any leftover ones (Core.apply revokes before hiding
     * and restores after un-hiding, because Android ignores permission changes on hidden apps).
     */
    static void record(Context c, Collection<String> blocked) {
        for (String pkg : revokedApps(c)) {
            if (!blocked.contains(pkg) && prefs(c).contains(pkg)) restore(c, pkg);
        }
        prefs(c).edit().putStringSet(KEY_REVOKED_APPS, new TreeSet<>(blocked)).commit();
    }

    static Set<String> revokedApps(Context c) {
        return new TreeSet<>(prefs(c).getStringSet(KEY_REVOKED_APPS, Collections.<String>emptySet()));
    }

    /** How many permissions each blocked app had that Anchor took away (and will give back). */
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
                continue;  // already revoked by Anchor
            }
            if (pm.checkPermission(perm, pkg) == PackageManager.PERMISSION_GRANTED && granted.add(perm)) {
                changed = true;
            }
            try {
                dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED);
            } catch (RuntimeException ignored) {
                // Some system apps have permissions Android won't let anyone change.
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
                // Grant again what the app had, then hand control back to the user.
                if (granted.contains(perm)) {
                    dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED);
                }
                dpm.setPermissionGrantState(admin, pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT);
            } catch (RuntimeException ignored) {
            }
        }
        prefs(c).edit().remove(pkg).commit();
    }

    /**
     * Details about one app for the computer's details window: version, dates, and each runtime
     * permission with its name as Android shows it, whether it's granted, and whether it's locked.
     */
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
        return new org.json.JSONObject()
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

    /**
     * Grants or removes one permission, then hands control back to the user (so it can still be
     * changed in the phone's Settings). Not while the app is blocked: its permissions are held back.
     */
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

    /** The app's "dangerous" permissions: the ones a user grants in a popup. */
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
                // Permission defined by an app that isn't installed.
            }
        }
        return out;
    }
}
