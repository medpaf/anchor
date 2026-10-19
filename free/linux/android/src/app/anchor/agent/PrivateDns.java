package app.anchor.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.UserManager;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * Pro: keeps the phone on the Private DNS provider chosen on the computer, by locking the setting.
 *
 * <p>The phone app never touches the network (it has no internet permission), so the computer checks
 * the provider and writes the setting over USB. This class only unlocks the setting just before that
 * write and locks it again right after, and both need the computer's key.
 */
final class PrivateDns {
    private static final String PREFS = "anchor_private_dns";
    private static final String KEY_HOST = "host";

    private PrivateDns() {
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** The provider the computer set, or null when the phone decides for itself. */
    static String host(Context c) {
        return prefs(c).getString(KEY_HOST, null);
    }

    static boolean locked(Context c) {
        UserManager um = c.getSystemService(UserManager.class);
        return um != null && um.hasUserRestriction(UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
    }

    /** Lets the computer write the setting for a moment. */
    static void unlock(Context c) {
        Core.dpm(c).clearUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
    }

    /** After the computer wrote the setting: remembers the provider and locks it (unlocked for null). */
    static void lock(Context c, String host) {
        prefs(c).edit().putString(KEY_HOST, host).commit();
        if (host != null) {
            Core.dpm(c).addUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
        } else {
            unlock(c);
        }
    }

    /** Locks again if the computer left it unlocked (say, the cable came out halfway through a change). */
    static void reapply(Context c) {
        if (host(c) != null && !locked(c)) {
            try {
                Core.dpm(c).addUserRestriction(Core.admin(c), UserManager.DISALLOW_CONFIG_PRIVATE_DNS);
            } catch (RuntimeException ignored) {
            }
        }
    }

    /** Anchor is being removed: the phone gets its own setting back. */
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
