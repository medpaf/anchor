package app.anchor.agent;

import android.content.Context;

final class Edition {
    static final String WEBSITE = "https://github.com/medpaf/anchor";
    private static final String DONATE_URL = "https://github.com/sponsors/medpaf";
    private static final String PREFS = "anchor_edition";
    private static final String KEY = "edition";

    private Edition() {
    }

    static void remember(Context c, String edition) {
        if (("free".equals(edition) || "pro".equals(edition)) && !edition.equals(get(c))) {
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, edition).apply();
        }
    }

    static String get(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "free");
    }

    static String name(Context c) {
        return "pro".equals(get(c)) ? "Anchor - Master" : "Anchor - Free";
    }

    static String donateUrl(Context c) {
        return "pro".equals(get(c)) ? null : DONATE_URL;
    }
}
