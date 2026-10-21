package app.anchor.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.UserManager;

import org.json.JSONException;
import org.json.JSONObject;

final class PrivateDns {
    private static final String PREFS = "anchor_private_dns";
    private static final String KEY_HOST = "host";

    private PrivateDns() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static String host(Context c) {
        return prefs(c).getString(KEY_HOST, null);
    }

    static boolean locked(Context c) {
        UserManager um = c.getSystemService(UserManager.class);
        return um != null && um.hasUserRestriction(UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
    }

    static void unlock(Context c) {
        Core.dpm(c).clearUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
    }

    static void lock(Context c, String host) {
        prefs(c).edit().putString(KEY_HOST, host).commit();
        if (host != null) {
            Core.dpm(c).addUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
        } else {
            unlock(c);
        }
    }

    static void reapply(Context c) {
        if (host(c) != null && !locked(c)) {
            try {
                Core.dpm(c).addUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
            } catch (RuntimeException ignored) {
            }
        }
    }

    static void release(Context c) {
        prefs(c).edit().remove(KEY_HOST).commit();
        try {
            unlock(c);
        } catch (RuntimeException ignored) {
        }
    }

    static JSONObject status(Context c) throws JSONException {
        String host = host(c);
        return new JSONObject().put("host", host == null ? JSONObject.NULL : host).put("locked", locked(c));
    }
}
