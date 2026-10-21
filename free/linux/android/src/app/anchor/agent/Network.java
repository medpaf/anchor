package app.anchor.agent;

import android.app.admin.DevicePolicyManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import org.json.JSONException;
import org.json.JSONObject;

final class Network {
    private static final String PREFS = "anchor_network";
    private static final String KEY_OFFLINE = "offline";
    private static final String KEY_NO_WIFI = "no_wifi";

    private static final String BLOCK_SSID = "Anchor blocks all Wi-Fi";

    private Network() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static boolean offline(Context c) {
        return prefs(c).getBoolean(KEY_OFFLINE, false);
    }

    static boolean noWifi(Context c) {
        return prefs(c).getBoolean(KEY_NO_WIFI, false);
    }

    static void setOffline(Context c, boolean on) throws CommandProvider.AgentError {
        try {
            Core.dpm(c).setAlwaysOnVpnPackage(Core.admin(c), on ? c.getPackageName() : null, on);
        } catch (PackageManager.NameNotFoundException | UnsupportedOperationException e) {
            throw new CommandProvider.AgentError("vpn_unsupported",
                    "This phone can't lock the VPN needed for offline mode");
        }
        prefs(c).edit().putBoolean(KEY_OFFLINE, on).commit();
    }

    static void setNoWifi(Context c, boolean on) throws CommandProvider.AgentError {
        if (Build.VERSION.SDK_INT < 33) {
            if (on) throw new CommandProvider.AgentError("wifi_unsupported",
                    "Blocking Wi-Fi needs Android 13 or newer");
            prefs(c).edit().putBoolean(KEY_NO_WIFI, false).commit();
            return;
        }
        applyWifi(c, on);
        prefs(c).edit().putBoolean(KEY_NO_WIFI, on).commit();
    }

    @android.annotation.TargetApi(33)
    private static void applyWifi(Context c, boolean on) {
        DevicePolicyManager dpm = Core.dpm(c);
        if (!on) {
            dpm.setWifiSsidPolicy(null);
            return;
        }
        java.util.Set<android.net.wifi.WifiSsid> ssids = new java.util.HashSet<>();
        ssids.add(android.net.wifi.WifiSsid.fromBytes(
                BLOCK_SSID.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        dpm.setWifiSsidPolicy(new android.app.admin.WifiSsidPolicy(
                android.app.admin.WifiSsidPolicy.WIFI_SSID_POLICY_TYPE_ALLOWLIST, ssids));
    }

    static void reapply(Context c) {
        try {
            if (offline(c) && !c.getPackageName().equals(Core.dpm(c).getAlwaysOnVpnPackage(Core.admin(c)))) {
                Core.dpm(c).setAlwaysOnVpnPackage(Core.admin(c), c.getPackageName(), true);
            }
        } catch (PackageManager.NameNotFoundException | RuntimeException ignored) {
        }
        try {
            if (noWifi(c) && Build.VERSION.SDK_INT >= 33) applyWifi(c, true);
        } catch (RuntimeException ignored) {
        }
    }

    static void release(Context c) {
        try {
            Core.dpm(c).setAlwaysOnVpnPackage(Core.admin(c), null, false);
        } catch (PackageManager.NameNotFoundException | RuntimeException ignored) {
        }
        try {
            if (Build.VERSION.SDK_INT >= 33) Core.dpm(c).setWifiSsidPolicy(null);
        } catch (RuntimeException ignored) {
        }
        prefs(c).edit().putBoolean(KEY_OFFLINE, false).putBoolean(KEY_NO_WIFI, false).commit();
    }

    static JSONObject status(Context c) throws JSONException {
        return new JSONObject()
                .put("offline", offline(c))
                .put("no_wifi", noWifi(c))
                .put("wifi_supported", Build.VERSION.SDK_INT >= 33);
    }
}
