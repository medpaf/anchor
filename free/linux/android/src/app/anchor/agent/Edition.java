package app.anchor.agent;

import android.content.Context;

/**
 * Free or Pro: the same phone app serves both, and the desktop app says which one it is with every
 * status call. Only what the phone shows depends on it (the name in About, Buy me a coffee); the
 * commands are the same, and the Pro ones are simply never used by the free desktop app.
 */
final class Edition {
    static final String WEBSITE = "https://github.com/medpaf/anchor";
    private static final String DONATE_URL = "https://github.com/sponsors/medpaf";
    private static final String PREFS = "anchor_edition";
    private static final String KEY = "edition";

    private Edition() {
    }

    /** From the desktop app: "free" or "pro". Anything else is ignored. */
    static void remember(Context c, String edition) {
        if (("free".equals(edition) || "pro".equals(edition)) && !edition.equals(get(c))) {
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, edition).apply();
        }
    }

    /** "free" until a desktop app said otherwise. */
    static String get(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "free");
    }

    /** Shown in About, like the desktop's window title. */
    static String name(Context c) {
        return "pro".equals(get(c)) ? "Anchor - Master" : "Anchor - Free";
    }

    /** Menu → Buy me a coffee… is in the free version only, like on the desktop. */
    static String donateUrl(Context c) {
        return "pro".equals(get(c)) ? null : DONATE_URL;
    }
}
