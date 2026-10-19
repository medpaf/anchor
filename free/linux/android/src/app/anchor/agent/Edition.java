package app.anchor.agent;

/** What differs between the free and the full version of the phone app, like the desktop's WINDOW_TITLE. */
final class Edition {
    /** Shown in About, like the desktop's window title. */
    static final String NAME = "Anchor - Free";
    static final String WEBSITE = "https://github.com/medpaf/anchor";
    /** Menu → Buy me a coffee… (free version only, like the desktop). */
    static final String DONATE_URL = "https://github.com/sponsors/medpaf";

    private Edition() {
    }
}
