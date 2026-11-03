package app.anchor.agent;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.Spannable;
import android.text.SpannableString;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

public class MainActivity extends Activity {

    private static int BG = 0xFF0D0A14;
    private static int CARD = 0xFF16121F;
    private static int TEXT = 0xFFEEEAF7;
    private static int DIM = 0x99EEEAF7;
    private static int ICON = 0xFFC4B5FD;
    private static int VIOLET = 0xFFB39DFF;
    private static int GREY = 0xFF9A93AD;
    private static final String UI_PREFS = "anchor_ui";
    private static final String THEME_KEY = "theme";
    private static final java.util.Map<Integer, Integer> RETRO = new java.util.HashMap<>();
    static {
        RETRO.put(0xFF0D0A14, 0xFF000000);
        RETRO.put(0xFF16121F, 0xFF000000);
        RETRO.put(0xFFEEEAF7, 0xFFFFF4E4);
        RETRO.put(0x99EEEAF7, 0xFFFFF4E4);
        RETRO.put(0xFFC4B5FD, 0xFFFFF4E4);
        RETRO.put(0xFF9A93AD, 0xFFFFF4E4);
        RETRO.put(0x0FFFFFFF, 0xCCFFF4E4);
        RETRO.put(0xFFFFFFFF, 0xFF000000);
        RETRO.put(0x14FFFFFF, 0x29FFF4E4);
        RETRO.put(0x0DFFFFFF, 0x29FFF4E4);
        RETRO.put(0x0AFFFFFF, 0x00000000);
        RETRO.put(0xFFE6E1F0, 0xFFFFF4E4);
        RETRO.put(0xFF6E6880, 0xFFFFF4E4);
        RETRO.put(0xFFE4DBFF, 0xFFFFF4E4);
        RETRO.put(0xA6A78BFA, 0xCCFFF4E4);
        RETRO.put(0xFF1A1525, 0xFF000000);
        RETRO.put(0x38FFFFFF, 0x66FFF4E4);
    }
    private static boolean retro;
    private static boolean systemFont;
    private static int accent = 0xFFC8574B;
    private static final String ACCENT_KEY = "accent";
    private static final String FONT_KEY = "font";
    private static final String[] ACCENT_NAMES = {"Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink", "White"};
    private static final int[] ACCENTS = {0xFFC8574B, 0xFFD98A52, 0xFFD9BC62, 0xFF67B886, 0xFF6C9FD1, 0xFFA391D1, 0xFFD17BA3, 0xFFEDE7DC};
    private Typeface retroFont;
    private boolean switchingTheme;

    private static int c(int standard) {
        if (!retro) return standard;
        Integer mapped = RETRO.get(standard);
        return mapped != null ? mapped : standard;
    }

    private void applyTheme() {
        android.content.SharedPreferences ui = getSharedPreferences(UI_PREFS, MODE_PRIVATE);
        retro = "retro".equals(ui.getString(THEME_KEY, "standard"));
        systemFont = "system".equals(ui.getString(FONT_KEY, "retro"));
        accent = ui.getInt(ACCENT_KEY, 0xFFC8574B);
        RETRO.put(0xFFB39DFF, accent);
        RETRO.put(0xFF6A47B5, accent);
        RETRO.put(0xFF7C3AED, accent);
        RETRO.put(0x298B5CF6, withAlpha(accent, 0x29));
        RETRO.put(0x228B5CF6, withAlpha(accent, 0x22));
        RETRO.put(0x668B5CF6, withAlpha(accent, 0x66));
        RETRO.put(0x478B5CF6, withAlpha(accent, 0x47));
        RETRO.put(0x008B5CF6, withAlpha(accent, 0x00));
        syncLauncherIcon();
        BG = c(0xFF0D0A14);
        CARD = c(0xFF16121F);
        TEXT = c(0xFFEEEAF7);
        DIM = c(0x99EEEAF7);
        ICON = c(0xFFC4B5FD);
        VIOLET = c(0xFFB39DFF);
        GREY = c(0xFF9A93AD);
        if (retro && retroFont == null) {
            int id = getResources().getIdentifier("retro_mono", "font", getPackageName());
            if (id != 0) retroFont = getResources().getFont(id);
        }
    }

    private static int withAlpha(int color, int alpha) {
        return (alpha << 24) | (color & 0xFFFFFF);
    }

    private static int shade(int color, float hueShift, float valueScale) {
        float[] hsv = new float[3];
        android.graphics.Color.colorToHSV(color, hsv);
        if (hsv[1] < 0.1f) return valueScale < 1f ? 0xFFD6D6D6 : color;
        hsv[0] = (hsv[0] + hueShift + 360f) % 360f;
        hsv[2] = Math.min(1f, hsv[2] * valueScale);
        return android.graphics.Color.HSVToColor(hsv);
    }

    private GradientDrawable accentGradient() {
        return new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{shade(accent, 6f, 1f), accent, shade(accent, 0f, 0.86f)});
    }

    private int stroke() {
        return Math.round(1.5f * getResources().getDisplayMetrics().density);
    }

    private void syncLauncherIcon() {
        android.content.pm.PackageManager pm = getPackageManager();
        String[][] aliases = {{".StandardLauncher", retro ? "off" : "on"}, {".RetroLauncher", retro ? "on" : "off"}};
        for (String[] alias : aliases) {
            android.content.ComponentName name = new android.content.ComponentName(getPackageName(), getPackageName() + alias[0]);
            int wanted = "on".equals(alias[1])
                    ? android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED
                    : android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_DISABLED;
            try {
                if (pm.getComponentEnabledSetting(name) != wanted) {
                    pm.setComponentEnabledSetting(name, wanted, android.content.pm.PackageManager.DONT_KILL_APP);
                }
            } catch (IllegalArgumentException ignored) {
            }
        }
    }

    private View retroWindow(View content) {
        content.setOnApplyWindowInsetsListener(null);
        LinearLayout window = new LinearLayout(this);
        window.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable frame = rounded(BG, dp(16));
        frame.setStroke(stroke(), c(0x0FFFFFFF));
        window.setBackground(frame);
        window.setClipToOutline(true);
        window.setPadding(stroke(), stroke(), stroke(), stroke());

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(14), 0, dp(4), 0);
        android.graphics.drawable.LayerDrawable barBackground = new android.graphics.drawable.LayerDrawable(
                new android.graphics.drawable.Drawable[]{accentGradient(), new android.graphics.drawable.ColorDrawable(0xFF000000)});
        barBackground.setLayerGravity(1, Gravity.BOTTOM | Gravity.FILL_HORIZONTAL);
        barBackground.setLayerHeight(1, stroke());
        bar.setBackground(barBackground);
        TextView name = text();
        name.setText("Anchor");
        name.setTextColor(0xFF000000);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        name.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        bar.addView(name, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        final ImageView[] menuHolder = new ImageView[1];
        menuHolder[0] = iconButton("ic_menu", 0xFF000000, false, "Menu", new Runnable() {
            @Override
            public void run() {
                showMenu(menuHolder[0]);
            }
        });
        bar.addView(menuHolder[0], new LinearLayout.LayoutParams(dp(42), dp(42)));
        window.addView(bar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(46)));
        window.addView(content, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        android.widget.FrameLayout outer = new android.widget.FrameLayout(this);
        outer.setBackgroundColor(BG);
        android.widget.FrameLayout.LayoutParams windowLp = new android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT, android.widget.FrameLayout.LayoutParams.MATCH_PARENT);
        windowLp.setMargins(dp(4), dp(4), dp(4), dp(4));
        outer.addView(window, windowLp);
        outer.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public android.view.WindowInsets onApplyWindowInsets(View v, android.view.WindowInsets insets) {
                int top, bottom;
                if (android.os.Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                    top = bars.top;
                    bottom = bars.bottom;
                } else {
                    top = insets.getSystemWindowInsetTop();
                    bottom = insets.getSystemWindowInsetBottom();
                }
                v.setPadding(0, top, 0, bottom);
                return insets;
            }
        });
        return outer;
    }

    private Typeface f(Typeface standard, boolean bold) {
        if (!retro || systemFont || retroFont == null) return standard;
        return Typeface.create(retroFont, bold ? Typeface.BOLD : Typeface.NORMAL);
    }

    private TextView text() {
        TextView view = new TextView(this);
        if (retro && !systemFont && retroFont != null) view.setTypeface(retroFont);
        return view;
    }

    private EditText editText() {
        EditText view = new EditText(this);
        if (retro && !systemFont && retroFont != null) view.setTypeface(retroFont);
        return view;
    }

    private Button button() {
        Button view = new Button(this);
        if (retro && !systemFont && retroFont != null) view.setTypeface(retroFont);
        return view;
    }

    private TextView pill;
    private TextView title;
    private TextView detail;
    private EditText search;
    private LinearLayout lists;
    private TextView modeBanner;

    private final List<View> searchable = new ArrayList<>();

    private final List<Object[]> sections = new ArrayList<>();
    private final java.util.Set<String> openSections = new java.util.HashSet<>();

    private final java.util.concurrent.ExecutorService worker = java.util.concurrent.Executors.newSingleThreadExecutor();

    private View screen;
    private boolean unlocked;
    private boolean prompting;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        applyTheme();
        if (savedInstanceState != null) unlocked = savedInstanceState.getBoolean("unlocked", false);
        if (getActionBar() != null) getActionBar().hide();
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setBackgroundColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setBackgroundColor(BG);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        int screenW = getResources().getDisplayMetrics().widthPixels;
        int screenH = getResources().getDisplayMetrics().heightPixels;
        boolean compact = screenH < screenW * 3 / 2;
        int hpad = screenW > dp(592) ? (screenW - dp(560)) / 2 : dp(16);
        root.setPadding(hpad, compact ? dp(12) : dp(28), hpad, dp(32));

        final ImageView menu = iconButton("ic_menu", TEXT, false, "Menu", null);
        menu.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showMenu(menu);
            }
        });
        LinearLayout.LayoutParams menuLp = new LinearLayout.LayoutParams(dp(42), dp(42));
        menuLp.gravity = Gravity.END;
        if (!retro) root.addView(menu, menuLp);

        ImageView icon = new ImageView(this);

        int orb = getResources().getIdentifier(retro ? "ic_fg_retro" : "ic_fg", "drawable", getPackageName());
        icon.setImageDrawable(orb != 0 ? getDrawable(orb) : getApplicationInfo().loadIcon(getPackageManager()));

        pill = text();
        pill.setTextSize(TypedValue.COMPLEX_UNIT_SP, compact ? 11 : 13);
        pill.setTypeface(f(Typeface.DEFAULT_BOLD, true));
        pill.setAllCaps(true);
        pill.setLetterSpacing(0.14f);
        pill.setPadding(dp(14), dp(6), dp(14), dp(6));

        title = text();
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, compact ? 22 : 32);
        title.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        title.setTextColor(TEXT);
        title.setLetterSpacing(-0.01f);

        detail = text();
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, compact ? 13 : 16);
        detail.setLineSpacing(0, 1.25f);
        detail.setTextColor(DIM);

        if (compact) {
            pill.setGravity(Gravity.START);
            title.setGravity(Gravity.START);
            detail.setGravity(Gravity.START);
            LinearLayout hero = new LinearLayout(this);
            hero.setOrientation(LinearLayout.HORIZONTAL);
            hero.setGravity(Gravity.CENTER_VERTICAL);
            hero.addView(icon, new LinearLayout.LayoutParams(dp(58), dp(58)));
            LinearLayout texts = new LinearLayout(this);
            texts.setOrientation(LinearLayout.VERTICAL);
            LinearLayout.LayoutParams pLp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            pLp.bottomMargin = dp(5);
            texts.addView(pill, pLp);
            texts.addView(title);
            LinearLayout.LayoutParams dLp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            dLp.topMargin = dp(4);
            texts.addView(detail, dLp);
            LinearLayout.LayoutParams tLp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
            tLp.leftMargin = dp(16);
            hero.addView(texts, tLp);
            root.addView(hero, fill(dp(4)));
        } else {
            title.setGravity(Gravity.CENTER);
            detail.setGravity(Gravity.CENTER);
            root.addView(icon, new LinearLayout.LayoutParams(dp(132), dp(132)));
            root.addView(pill, centered(dp(28)));
            root.addView(title, centered(dp(14)));
            LinearLayout.LayoutParams dlp = centered(dp(12));
            dlp.leftMargin = dlp.rightMargin = dp(8);
            root.addView(detail, dlp);
        }

        modeBanner = text();
        modeBanner.setTextColor(TEXT);
        modeBanner.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        modeBanner.setPadding(dp(16), dp(12), dp(16), dp(12));
        modeBanner.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(14)));
        modeBanner.setVisibility(View.GONE);
        root.addView(modeBanner, fill(dp(16)));

        search = editText();
        search.setHint("Search your apps");
        search.setHintTextColor(GREY);
        search.setTextColor(TEXT);
        search.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        search.setSingleLine(true);
        search.setBackground(null);
        search.setPadding(dp(10), dp(12), 0, dp(12));
        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int a, int b, int c) {
            }

            @Override
            public void onTextChanged(CharSequence s, int a, int b, int c) {
                filter();
            }

            @Override
            public void afterTextChanged(Editable e) {
            }
        });

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.HORIZONTAL);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setPadding(dp(14), 0, dp(14), 0);
        box.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(14)));
        box.addView(icon("ic_search", GREY), new LinearLayout.LayoutParams(dp(18), dp(18)));
        box.addView(search, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(box, fill(dp(28)));

        lists = new LinearLayout(this);
        lists.setOrientation(LinearLayout.VERTICAL);
        root.addView(lists, fill(0));

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        scroll.setFillViewport(true);
        scroll.addView(root);

        scroll.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public android.view.WindowInsets onApplyWindowInsets(View v, android.view.WindowInsets insets) {
                int top, bottom;
                if (android.os.Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                    top = bars.top;
                    bottom = bars.bottom;
                } else {
                    top = insets.getSystemWindowInsetTop();
                    bottom = insets.getSystemWindowInsetBottom();
                }
                v.setPadding(0, top, 0, bottom);
                return insets;
            }
        });
        screen = retro ? retroWindow(scroll) : scroll;
        setContentView(screen);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (unlocked || !hasScreenLock()) {
            unlocked = true;
            screen.setVisibility(View.VISIBLE);
            refresh();
            return;
        }
        screen.setVisibility(View.INVISIBLE);
        if (!prompting) askToUnlock();
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (!prompting && !switchingTheme) unlocked = false;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putBoolean("unlocked", switchingTheme && unlocked);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        worker.shutdown();
    }

    private void inBackground(final Runnable work, final Runnable after) {
        worker.execute(new Runnable() {
            @Override
            public void run() {
                work.run();
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (!isFinishing() && !isDestroyed()) after.run();
                    }
                });
            }
        });
    }

    private boolean hasScreenLock() {
        android.app.KeyguardManager km = getSystemService(android.app.KeyguardManager.class);
        return km != null && km.isDeviceSecure();
    }

    @SuppressWarnings("deprecation")
    private void askToUnlock() {
        prompting = true;
        android.hardware.biometrics.BiometricPrompt.Builder prompt =
                new android.hardware.biometrics.BiometricPrompt.Builder(this)
                        .setTitle("Unlock Anchor")
                        .setSubtitle("Use your fingerprint, or your phone's PIN or pattern");
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            prompt.setAllowedAuthenticators(android.hardware.biometrics.BiometricManager.Authenticators.BIOMETRIC_WEAK
                    | android.hardware.biometrics.BiometricManager.Authenticators.DEVICE_CREDENTIAL);
        } else {
            prompt.setDeviceCredentialAllowed(true);
        }
        prompt.build().authenticate(new android.os.CancellationSignal(), getMainExecutor(),
                new android.hardware.biometrics.BiometricPrompt.AuthenticationCallback() {
                    @Override
                    public void onAuthenticationSucceeded(android.hardware.biometrics.BiometricPrompt.AuthenticationResult r) {
                        prompting = false;
                        unlocked = true;
                        screen.setVisibility(View.VISIBLE);
                        refresh();
                    }

                    @Override
                    public void onAuthenticationError(int code, CharSequence message) {
                        prompting = false;
                        finish();
                    }
                });
    }

    private void refresh() {
        boolean ready = Core.isOwner(this) && Core.isPaired(this);
        long now = System.currentTimeMillis();
        String mode = Core.mode(this, now);
        long ends = Core.shiftEnds(this, now);

        Map<String, String> anchored = new TreeMap<>();
        if (ready && mode != null) {
            for (String pkg : Core.selected(this)) {
                if (Core.isInstalled(this, pkg)) anchored.put(pkg, ends > 0 ? "Hidden until " + time(ends, now) : "Hidden");
            }
        }
        if (ready) {
            for (Map.Entry<String, Long> e : Core.scheduledNow(this, now).entrySet()) {
                if (!anchored.containsKey(e.getKey())) {
                    anchored.put(e.getKey(), "Hidden by its schedule until " + time(e.getValue(), now));
                }
            }
        }

        if (!ready) {
            setPill("Setup needed", GREY);
            title.setText("Almost there");
            detail.setText("Connect this phone to your computer and open Anchor to finish setup.");
        } else if (!anchored.isEmpty()) {
            setPill(mode != null ? "●  Anchored" : "●  On schedule", VIOLET);
            title.setText(count(anchored.size(), "app") + " hidden");
            String when;
            if (mode != null && ends > 0) {
                when = "They come back by themselves at " + time(ends, now) + ", with all their data. ";
            } else if (mode != null) {
                when = "They'll come back exactly as they were, with all their data, when you release them. ";
            } else {
                when = "Hidden by their schedules. Each one comes back by itself when its schedule ends. ";
            }
            detail.setText(when + "To release sooner, connect this phone to your computer with a USB cable and open Anchor.");
        } else {
            setPill("Not anchored", GREY);
            title.setText("You're free");
            detail.setText("Tap Anchor on any app below to hide it. Only your computer can release it.");
        }

        lists.removeAllViews();
        searchable.clear();
        sections.clear();

        boolean pro = "pro".equals(Edition.get(this));
        String mlabel = Core.modeLabel(this);
        if (ready && pro && mlabel != null && !mlabel.isEmpty()) {
            SpannableString banner = new SpannableString("●  " + mlabel + " mode is on · set from your computer");
            int nameStart = 3;
            int nameEnd = nameStart + mlabel.length();
            banner.setSpan(new ForegroundColorSpan(VIOLET), nameStart, nameEnd, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            banner.setSpan(new StyleSpan(Typeface.BOLD), nameStart, nameEnd, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            modeBanner.setText(banner);
            modeBanner.setVisibility(View.VISIBLE);
        } else {
            modeBanner.setVisibility(View.GONE);
        }
        if (!ready) return;

        Set<String> kept = InstallBlocks.kept(this);
        Set<String> caught = InstallBlocks.caught(this);
        List<String[]> never = new ArrayList<>();
        for (Map.Entry<String, String> e : InstallBlocks.names(this).entrySet()) {
            String pkg = e.getKey();
            String note = kept.contains(pkg) ? "Already on this phone, so not affected" : caught.contains(pkg) ? "Hidden" : pkg;
            never.add(new String[]{pkg, e.getValue(), note});
        }
        sortByName(never);

        List<String[]> hidden = new ArrayList<>();
        for (Map.Entry<String, String> e : anchored.entrySet()) {
            hidden.add(new String[]{e.getKey(), label(e.getKey()), e.getValue()});
        }
        sortByName(hidden);

        List<String[]> others = new ArrayList<>();
        PackageManager pm = getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        Set<String> seen = new TreeSet<>();
        for (ResolveInfo ri : pm.queryIntentActivities(launcher, 0)) {
            String pkg = ri.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || anchored.containsKey(pkg) || !seen.add(pkg)) continue;
            String note = schedulesFor(pkg).isEmpty() ? pkg : scheduleSummary(pkg);
            others.add(new String[]{pkg, String.valueOf(ri.activityInfo.applicationInfo.loadLabel(pm)), note});
        }
        sortByName(others);

        addSection("Never allow", "Apps that can't be installed.", "ic_block", never, false, false);
        if (!hidden.isEmpty()) {
            addSection("Anchored apps", "Hidden from this phone. Only your computer can release them.",
                    "ic_anchor", hidden, true, false);
        }
        if (!others.isEmpty()) {
            addSection(hidden.isEmpty() ? "Your apps" : "All other apps",
                    "Tap Anchor to hide an app from this phone right away.", "ic_grid", others, true, true);
        }
        if (pro) addAppTimers();
        if (pro) addSystemSettings();
        filter();
    }

    private void addSystemSettings() {
        String dns = PrivateDns.host(this);
        boolean reset = Core.factoryResetLocked(this);
        boolean offline = Network.offline(this);
        boolean noWifi = Network.noWifi(this);

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(4), 0, dp(4), 0);

        boolean wifiOk = android.os.Build.VERSION.SDK_INT >= 33;

        final Runnable offlineOn = new Runnable() {
            @Override public void run() {
                try { Network.setOffline(MainActivity.this, true); } catch (CommandProvider.AgentError e) {
                    Toast.makeText(MainActivity.this, e.getMessage(), Toast.LENGTH_LONG).show();
                }
                refresh();
            }
        };
        final Runnable wifiOn = new Runnable() {
            @Override public void run() {
                try { Network.setNoWifi(MainActivity.this, true); } catch (CommandProvider.AgentError e) {
                    Toast.makeText(MainActivity.this, e.getMessage(), Toast.LENGTH_LONG).show();
                }
                refresh();
            }
        };
        final Runnable resetOn = new Runnable() {
            @Override public void run() {
                try { Core.lockFactoryReset(MainActivity.this, true); } catch (RuntimeException ignored) { }
                refresh();
            }
        };

        box.addView(settingsHead("Network", true));
        addSettingRow(box, true, "Offline",
                "Blocks all Internet, over Wi-Fi and cellular. Uses the phone's VPN slot. If you have "
                + "another VPN, it disconnects while this is on, and you'll need to turn it back on "
                + "manually after you turn this off.", offline ? "On" : "Off",
                offline ? lockedTap("Offline") : tightenTap("Turn on Offline?",
                        "This cuts all Internet on your phone — Wi-Fi and cellular. Only your computer "
                        + "can turn it back off.", offlineOn));
        addSettingRow(box, false, "Block Wi-Fi", "Stops the phone joining any Wi-Fi network.",
                noWifi ? "On" : "Off",
                noWifi ? lockedTap("Block Wi-Fi") : (wifiOk ? tightenTap("Turn on Block Wi-Fi?",
                        "The phone won't join any Wi-Fi network. Only your computer can turn it back off.",
                        wifiOn) : infoTap("Blocking Wi-Fi needs Android 13 or newer.")));
        addSettingRow(box, false, "Content filter (Private DNS)",
                "Blocks whole kinds of websites in every app and browser.",
                dns != null ? contentFilterName(dns) : "Off",
                infoTap("The content filter is set from your computer."));

        box.addView(settingsHead("Protection", false));
        addSettingRow(box, true, "Prevent factory reset",
                "Greys out \"Erase all data\" in the phone's Settings.", reset ? "On" : "Off",
                reset ? lockedTap("Prevent factory reset") : tightenTap("Turn on Prevent factory reset?",
                        "Greys out \"Erase all data\" in the phone's Settings. Only your computer can turn "
                        + "it back off.", resetOn));

        lists.addView(box, fill(dp(14)));
    }

    private void addAppTimers() {
        java.util.Map<String, Integer> timers = Core.timers(this);
        if (timers.isEmpty()) return;
        long now = System.currentTimeMillis();
        java.util.Map<String, Long> usage = Core.usageToday(this, now);
        java.util.Map<String, Long> timedOut = Core.timedOutNow(this, now);
        PackageManager pm = getPackageManager();

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(4), 0, dp(4), 0);
        box.addView(settingsHead("App timers", true));
        Runnable info = infoTap("App timers are set from your computer. They reset at midnight.");
        boolean first = true;
        for (java.util.Map.Entry<String, Integer> e : timers.entrySet()) {
            String pkg = e.getKey();
            long limitMs = e.getValue() * 60_000L;
            String name;
            try {
                name = String.valueOf(pm.getApplicationInfo(pkg, 0).loadLabel(pm));
            } catch (PackageManager.NameNotFoundException ex) {
                name = pkg;
            }
            String value;
            if (timedOut.containsKey(pkg)) {
                value = "Used up";
            } else {
                long used = usage.containsKey(pkg) ? usage.get(pkg) : 0;
                value = screenTime(Math.max(0, limitMs - used)) + " left";
            }
            addSettingRow(box, first, name, screenTime(limitMs) + " a day", value, info);
            first = false;
        }
        lists.addView(box, fill(dp(14)));
    }

    private Runnable tightenTap(final String heading, final String message, final Runnable apply) {
        return new Runnable() {
            @Override public void run() { confirmTighten(heading, message, apply); }
        };
    }

    private Runnable lockedTap(final String label) {
        return new Runnable() {
            @Override public void run() {
                Toast.makeText(MainActivity.this, label + " is on. Only your computer can turn it off.",
                        Toast.LENGTH_SHORT).show();
            }
        };
    }

    private Runnable infoTap(final String message) {
        return new Runnable() {
            @Override public void run() { Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show(); }
        };
    }

    private void confirmTighten(String heading, String message, final Runnable onYes) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading(heading), centered(0));
        box.addView(dialogText(message), centered(dp(8)));
        Button cancel = pillButton("Cancel", false);
        Button go = pillButton("Turn on", true);
        cancel.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { dialog.dismiss(); }
        });
        go.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { dialog.dismiss(); onYes.run(); }
        });
        box.addView(twoButtons(cancel, go), fill(dp(22)));
        showDialog(dialog, box);
    }

    private TextView settingsHead(String text, boolean firstGroup) {
        TextView t = groupTitle(text);
        t.setPadding(dp(4), firstGroup ? 0 : dp(18), 0, dp(4));
        return t;
    }

    private void addSettingRow(LinearLayout box, boolean first, String label, String subtitle, String value,
                               final Runnable onTap) {
        if (!first) box.addView(divider());
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(13), 0, dp(13));
        if (onTap != null) {
            row.setClickable(true);
            row.setBackground(new android.graphics.drawable.RippleDrawable(
                    ColorStateList.valueOf(c(0x228B5CF6)), null, new android.graphics.drawable.ColorDrawable(c(0xFFFFFFFF))));
            row.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { onTap.run(); }
            });
        }
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        TextView l = text();
        l.setText(label);
        l.setTextColor(TEXT);
        l.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        col.addView(l);
        TextView s = text();
        s.setText(subtitle);
        s.setTextColor(DIM);
        s.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        s.setLineSpacing(0, 1.2f);
        s.setPadding(0, dp(2), 0, 0);
        col.addView(s);
        row.addView(col, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        TextView v = text();
        v.setText(value);
        v.setTextColor("Off".equals(value) ? GREY : VIOLET);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        v.setTypeface(f(Typeface.DEFAULT_BOLD, true));
        LinearLayout.LayoutParams vlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        vlp.leftMargin = dp(12);
        row.addView(v, vlp);
        box.addView(row);
    }

    private String contentFilterName(String host) {
        if ("family.cloudflare-dns.com".equals(host)) return "Cloudflare Family";
        if ("family.adguard-dns.com".equals(host)) return "AdGuard Family";
        if ("dns.quad9.net".equals(host)) return "Quad9";
        return "Custom filter";
    }

    private void addSection(String name, String hint, String logo, List<String[]> rows,
                            boolean icons, boolean anchorButtons) {
        final String key = "folded_" + logo;

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(18)));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(16), dp(12), dp(16), dp(12));
        header.setClickable(true);
        header.addView(icon(logo, ICON), new LinearLayout.LayoutParams(dp(20), dp(20)));
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        text.setPadding(dp(14), 0, dp(8), 0);
        TextView t = text();
        t.setText(name + " (" + rows.size() + ")");
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        text.addView(t);
        TextView h = text();
        h.setText(hint);
        h.setTextColor(DIM);
        h.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        text.addView(h);
        header.addView(text, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        final ImageView chevron = icon("ic_expand_more", GREY);
        header.addView(chevron, new LinearLayout.LayoutParams(dp(22), dp(22)));
        card.addView(header);

        final LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        for (String[] r : rows) {
            View row = row(r[0], r[1], r[2], icons, anchorButtons);
            row.setTag((r[1] + " " + r[0]).toLowerCase());
            searchable.add(row);
            body.addView(divider());
            body.addView(row);
        }
        card.addView(body);

        boolean folded = !openSections.contains(key);
        body.setVisibility(folded ? View.GONE : View.VISIBLE);

        setIcon(chevron, folded ? "ic_expand_less" : "ic_expand_more", GREY);
        header.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                boolean nowFolded = body.getVisibility() == View.VISIBLE;
                body.setVisibility(nowFolded ? View.GONE : View.VISIBLE);
                setIcon(chevron, nowFolded ? "ic_expand_less" : "ic_expand_more", GREY);
                if (nowFolded) openSections.remove(key);
                else openSections.add(key);
            }
        });
        sections.add(new Object[]{body, chevron, key});
        lists.addView(card, fill(dp(14)));
    }

    private View row(final String pkg, final String name, String note, boolean withIcon, boolean anchorButton) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(10), dp(14), dp(10));
        if (withIcon) {

            row.setBackground(new android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(c(0x228B5CF6)), null,
                    new android.graphics.drawable.ColorDrawable(c(0xFFFFFFFF))));
            row.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    showDetails(pkg, name);
                }
            });
            ImageView icon = new ImageView(this);
            Drawable d = appIcon(pkg);
            if (d != null) icon.setImageDrawable(d);
            LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(dp(36), dp(36));
            ip.rightMargin = dp(12);
            row.addView(icon, ip);
        }
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        TextView label = text();
        label.setText(name);
        label.setTextColor(TEXT);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        label.setSingleLine(true);
        label.setEllipsize(TextUtils.TruncateAt.END);
        text.addView(label);
        if (!note.isEmpty()) {
            TextView n = text();
            n.setText(note);
            n.setTextColor(DIM);
            n.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            n.setSingleLine(true);
            n.setEllipsize(TextUtils.TruncateAt.MIDDLE);
            text.addView(n);
        }
        row.addView(text, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        if (anchorButton) {
            LinearLayout.LayoutParams ib = new LinearLayout.LayoutParams(dp(38), dp(38));
            ib.leftMargin = dp(4);
            if (canUninstall(pkg)) {
                row.addView(iconButton("ic_delete", GREY, false, "Uninstall " + name, new Runnable() {
                    @Override
                    public void run() {
                        confirmUninstall(pkg, name);
                    }
                }), ib);
            }
            boolean scheduled = !schedulesFor(pkg).isEmpty();
            row.addView(iconButton("ic_alarm", scheduled ? VIOLET : GREY, scheduled, "Schedule for " + name, new Runnable() {
                @Override
                public void run() {
                    showSchedules(pkg, name);
                }
            }), ib);
        }
        if (anchorButton) {
            Button anchor = button();
            anchor.setText("Anchor");
            anchor.setAllCaps(false);
            anchor.setTextColor(c(0xFFFFFFFF));
            anchor.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            anchor.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
            anchor.setMinHeight(0);
            anchor.setMinimumHeight(0);
            anchor.setMinWidth(0);
            anchor.setMinimumWidth(0);
            anchor.setPadding(dp(18), dp(8), dp(18), dp(8));
            GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                    new int[]{c(0xFF6A47B5), c(0xFF6A47B5)});
            bg.setCornerRadius(dp(99));
            anchor.setBackground(bg);
            anchor.setStateListAnimator(null);
            anchor.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    confirmAnchor(pkg, name);
                }
            });
            LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            bp.leftMargin = dp(10);
            row.addView(anchor, bp);
        }
        return row;
    }

    private void confirmAnchor(final String pkg, final String name) {
        String message = "It's hidden from this phone right away, and only your computer can bring it back.";
        if (cameWithPhone(pkg)) {
            message = name + " came with your phone, so hiding it can stop some of the phone's features from "
                    + "working. " + message;
        }
        confirm(pkg, "Anchor " + name + "?", message,
                "Anchor", false, new Runnable() {
                    @Override
                    public void run() {
                        anchorApp(pkg, name);
                    }
                });
    }

    private void confirmUninstall(final String pkg, final String name) {
        confirm(pkg, "Uninstall " + name + "?", name + " and its data are removed from this phone.",
                "Uninstall", true, new Runnable() {
                    @Override
                    public void run() {
                        uninstallApp(pkg, name);
                    }
                });
    }

    private void showMenu(View anchor) {
        android.widget.PopupMenu popup = new android.widget.PopupMenu(
                new android.view.ContextThemeWrapper(this, android.R.style.Theme_DeviceDefault), anchor);
        final int donate = 1, about = 2, settings = 3;
        final String donateUrl = Edition.donateUrl(this);
        if (donateUrl != null) popup.getMenu().add(0, donate, 0, "Buy me a coffee…");
        popup.getMenu().add(0, settings, 1, "Settings");
        popup.getMenu().add(0, about, 2, "About Anchor");
        popup.setOnMenuItemClickListener(new android.widget.PopupMenu.OnMenuItemClickListener() {
            @Override
            public boolean onMenuItemClick(android.view.MenuItem item) {
                if (item.getItemId() == donate) openLink(donateUrl);
                if (item.getItemId() == about) showAbout();
                if (item.getItemId() == settings) showSettings();
                return true;
            }
        });
        popup.show();
    }

    private void showAbout() {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        ImageView logo = new ImageView(this);
        int orb = getResources().getIdentifier(retro ? "ic_fg_retro" : "ic_fg", "drawable", getPackageName());
        if (orb != 0) logo.setImageDrawable(getDrawable(orb));
        box.addView(logo, new LinearLayout.LayoutParams(dp(112), dp(112)));
        box.addView(dialogHeading(Edition.name(this)), centered(dp(4)));
        box.addView(dialogText("Block distracting apps on your Android phone. Only your computer can unblock them."),
                centered(dp(10)));
        TextView by = groupTitle("Developed by");
        box.addView(by, fill(dp(20)));
        LinearLayout credits = new LinearLayout(this);
        credits.setOrientation(LinearLayout.VERTICAL);
        credits.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
        credits.addView(twoLines("Paulo Medeiros", "", TEXT), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        credits.getChildAt(0).setPadding(dp(14), dp(12), dp(14), dp(12));
        box.addView(credits, fill(dp(8)));

        Button site = pillButton("GitHub repository", false);
        site.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                openLink(Edition.WEBSITE);
            }
        });
        Button back = pillButton("Back", false);
        back.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        box.addView(twoButtons(back, site), fill(dp(22)));
        showDialog(dialog, box);
    }

    private void showSettings() {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading("Settings"), centered(0));
        box.addView(groupTitle("Theme"), fill(dp(20)));
        LinearLayout choices = new LinearLayout(this);
        choices.setOrientation(LinearLayout.VERTICAL);
        choices.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
        String[][] themes = {{"standard", "Standard"}, {"retro", "Retro"}};
        for (int i = 0; i < themes.length; i++) {
            final String key = themes[i][0];
            choices.addView(choiceRow(themes[i][1], retro == key.equals("retro"), 0, new Runnable() {
                @Override
                public void run() {
                    dialog.dismiss();
                    if (retro != key.equals("retro")) saveUi(THEME_KEY, key);
                }
            }));
        }
        box.addView(choices, fill(dp(8)));
        if (retro) {
            box.addView(groupTitle("Accent color"), fill(dp(20)));
            LinearLayout accents = new LinearLayout(this);
            accents.setOrientation(LinearLayout.VERTICAL);
            accents.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
            boolean preset = false;
            for (int i = 0; i < ACCENTS.length; i++) {
                final int color = ACCENTS[i];
                if (color == accent) preset = true;
                accents.addView(choiceRow(ACCENT_NAMES[i], color == accent, color, new Runnable() {
                    @Override
                    public void run() {
                        dialog.dismiss();
                        if (color != accent) saveAccent(color);
                    }
                }));
            }
            accents.addView(choiceRow(preset ? "Custom…" : String.format("Custom  #%06X", accent & 0xFFFFFF), !preset, preset ? 0 : accent, new Runnable() {
                @Override
                public void run() {
                    dialog.dismiss();
                    showCustomAccent();
                }
            }));
            box.addView(accents, fill(dp(8)));
            box.addView(groupTitle("Font"), fill(dp(20)));
            LinearLayout fonts = new LinearLayout(this);
            fonts.setOrientation(LinearLayout.VERTICAL);
            fonts.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
            String[][] fontChoices = {{"retro", "Ubuntu Mono"}, {"system", "System font"}};
            for (String[] choice : fontChoices) {
                final String key = choice[0];
                fonts.addView(choiceRow(choice[1], systemFont == key.equals("system"), 0, new Runnable() {
                    @Override
                    public void run() {
                        dialog.dismiss();
                        if (systemFont != key.equals("system")) saveUi(FONT_KEY, key);
                    }
                }));
            }
            box.addView(fonts, fill(dp(8)));
        }
        Button back = pillButton("Back", false);
        back.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        box.addView(back, fill(dp(22)));
        showDialog(dialog, box);
    }

    private View choiceRow(String label, boolean chosen, int swatch, final Runnable onPick) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(13), dp(14), dp(13));
        if (swatch != 0) {
            View chip = new View(this);
            GradientDrawable swatchShape = rounded(swatch, dp(6));
            swatchShape.setStroke(stroke(), c(0x0FFFFFFF));
            chip.setBackground(swatchShape);
            LinearLayout.LayoutParams chipLp = new LinearLayout.LayoutParams(dp(22), dp(22));
            chipLp.rightMargin = dp(12);
            row.addView(chip, chipLp);
        }
        TextView name = text();
        name.setText(label);
        name.setTextColor(TEXT);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        row.addView(name, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        TextView mark = text();
        mark.setText(chosen ? "●" : "○");
        mark.setTextColor(chosen ? VIOLET : DIM);
        mark.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        row.addView(mark);
        row.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                onPick.run();
            }
        });
        row.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return row;
    }

    private void saveUi(String key, String value) {
        getSharedPreferences(UI_PREFS, MODE_PRIVATE).edit().putString(key, value).apply();
        switchingTheme = true;
        recreate();
    }

    private void saveAccent(int color) {
        getSharedPreferences(UI_PREFS, MODE_PRIVATE).edit().putInt(ACCENT_KEY, color).apply();
        switchingTheme = true;
        recreate();
    }

    private void showCustomAccent() {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading("Custom color"), centered(0));
        box.addView(dialogText("Type a color code, like C8574B."), centered(dp(10)));
        final EditText code = editText();
        code.setText(String.format("%06X", accent & 0xFFFFFF));
        code.setTextColor(TEXT);
        code.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        code.setSingleLine(true);
        code.setGravity(Gravity.CENTER);
        code.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(7), new android.text.InputFilter.AllCaps()});
        code.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(12)));
        code.setPadding(dp(12), dp(12), dp(12), dp(12));
        box.addView(code, fill(dp(16)));
        Button cancel = pillButton("Cancel", false);
        cancel.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        Button save = pillButton("Save", true);
        save.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String typed = code.getText().toString().replace("#", "").trim();
                if (!typed.matches("[0-9A-F]{6}")) {
                    Toast.makeText(MainActivity.this, "Use 6 characters from 0-9 and A-F", Toast.LENGTH_SHORT).show();
                    return;
                }
                dialog.dismiss();
                saveAccent(0xFF000000 | Integer.parseInt(typed, 16));
            }
        });
        box.addView(twoButtons(cancel, save), fill(dp(22)));
        showDialog(dialog, box);
    }

    private void openLink(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)));
        } catch (android.content.ActivityNotFoundException e) {
            Toast.makeText(this, "No browser to open " + url, Toast.LENGTH_LONG).show();
        }
    }

    private void showDetails(final String pkg, final String name) {
        final org.json.JSONObject info;
        try {
            info = Permissions.info(this, pkg);
        } catch (Exception e) {
            Toast.makeText(this, "Couldn't read " + name + "'s details: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }

        final android.app.Dialog dialog = new android.app.Dialog(this, android.R.style.Theme_DeviceDefault_NoActionBar);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setBackgroundColor(BG);
        ImageView icon = new ImageView(this);
        Drawable d = appIcon(pkg);
        if (d != null) icon.setImageDrawable(d);
        box.addView(icon, new LinearLayout.LayoutParams(dp(64), dp(64)));
        box.addView(dialogHeading(name), centered(dp(12)));
        TextView pkgText = dialogText(pkg);
        pkgText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        pkgText.setTextIsSelectable(true);
        box.addView(pkgText, centered(dp(2)));

        box.addView(groupTitle("About"), fill(dp(20)));
        LinearLayout about = new LinearLayout(this);
        about.setOrientation(LinearLayout.VERTICAL);
        about.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
        List<String[]> factList = new ArrayList<>();
        factList.add(new String[]{"Status", statusText(pkg)});
        if (info.has("usage_today")) {
            factList.add(new String[]{"Screen time today", screenTime(info.optLong("usage_today"))});
            factList.add(new String[]{"Screen time, last 7 days", screenTime(info.optLong("usage_week"))});
        }
        String[][] facts = {
                {"Version", info.optString("version").isEmpty() ? "—" : info.optString("version")},
                {"Installed", date(info.optLong("installed"))},
                {"Last updated", date(info.optLong("updated"))},
                {"Type", info.optBoolean("system") ? "Came with the phone" : "Installed by you"},
        };
        Collections.addAll(factList, facts);
        for (int i = 0; i < factList.size(); i++) {
            if (i > 0) about.addView(divider());
            about.addView(fact(factList.get(i)[0], factList.get(i)[1]));
        }
        box.addView(about, fill(dp(8)));

        box.addView(groupTitle("Permissions"), fill(dp(20)));
        final LinearLayout perms = new LinearLayout(this);
        perms.setOrientation(LinearLayout.VERTICAL);
        final TextView permsNote = text();
        permsNote.setTextColor(DIM);
        permsNote.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        permsNote.setLineSpacing(0, 1.2f);
        box.addView(permsNote, fill(dp(2)));
        box.addView(perms, fill(dp(8)));
        fillPermissions(perms, permsNote, pkg, name, info);

        if (canUninstall(pkg)) {
            Button uninstall = dangerButton("Uninstall");
            uninstall.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    dialog.dismiss();
                    confirmUninstall(pkg, name);
                }
            });
            box.addView(uninstall, fill(dp(24)));
        }

        Button done = pillButton("Back", false);
        done.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        box.addView(done, fill(dp(20)));

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        scroll.setFillViewport(true);
        scroll.addView(box);
        showFullScreen(dialog, scroll, box);
    }

    private void fillPermissions(final LinearLayout perms, TextView note, final String pkg, final String name,
                                 org.json.JSONObject info) {
        perms.removeAllViews();
        boolean blocked = info.optBoolean("blocked");
        note.setText(blocked
                ? "Permissions are removed while " + name + " is blocked, and come back when your computer releases it."
                : "Changes apply right away. You can still change them in the phone's Settings.");
        org.json.JSONArray list = info.optJSONArray("permissions");
        if (list == null || list.length() == 0) {
            perms.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
            perms.addView(fact("No permissions to manage", name + " doesn't ask for any permissions you grant."));
            return;
        }
        List<Object[]> rows = new ArrayList<>();
        for (int i = 0; i < list.length(); i++) {
            org.json.JSONObject p = list.optJSONObject(i);
            String[] names = PermNames.friendly(p.optString("name"), p.optString("label"));
            rows.add(new Object[]{names[0], names[1], p});
        }
        Collections.sort(rows, new Comparator<Object[]>() {
            @Override
            public int compare(Object[] a, Object[] b) {
                return ((String) a[0]).compareToIgnoreCase((String) b[0]);
            }
        });
        perms.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
        for (Object[] r : rows) {
            final org.json.JSONObject p = (org.json.JSONObject) r[2];
            final String titleText = (String) r[0];
            String subtitle = (String) r[1];
            if (blocked && p.optBoolean("had")) {
                subtitle = subtitle.isEmpty() ? "Comes back when released" : subtitle + " · comes back when released";
            }
            if (perms.getChildCount() > 0) perms.addView(divider());
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(14), dp(10), dp(10), dp(10));
            row.addView(twoLines(titleText, subtitle, TEXT),
                    new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
            final android.widget.Switch sw = new android.widget.Switch(this);
            sw.setChecked(p.optBoolean("granted"));
            sw.setEnabled(!blocked);
            styleSwitch(sw);
            sw.setContentDescription(titleText);
            sw.setOnCheckedChangeListener(new android.widget.CompoundButton.OnCheckedChangeListener() {
                @Override
                public void onCheckedChanged(android.widget.CompoundButton b, boolean grant) {
                    try {
                        Permissions.set(MainActivity.this, pkg, p.optString("name"), grant);
                        Toast.makeText(MainActivity.this, titleText + ": " + (grant ? "allowed" : "removed")
                                + " for " + name, Toast.LENGTH_SHORT).show();
                    } catch (RuntimeException e) {
                        b.setOnCheckedChangeListener(null);
                        b.setChecked(!grant);
                        b.setOnCheckedChangeListener(this);
                        Toast.makeText(MainActivity.this, "Couldn't change that permission: " + e.getMessage(),
                                Toast.LENGTH_LONG).show();
                    }
                }
            });

            sw.setShowText(false);
            android.widget.FrameLayout slot = new android.widget.FrameLayout(this);
            android.widget.FrameLayout.LayoutParams swLp = new android.widget.FrameLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.END | Gravity.CENTER_VERTICAL);
            slot.addView(sw, swLp);
            LinearLayout.LayoutParams slotLp = new LinearLayout.LayoutParams(dp(60), LinearLayout.LayoutParams.WRAP_CONTENT);
            slotLp.leftMargin = dp(8);
            row.addView(slot, slotLp);
            perms.addView(row);
        }
    }

    private void styleSwitch(android.widget.Switch sw) {
        int[][] states = {{-android.R.attr.state_enabled}, {android.R.attr.state_checked}, {}};

        GradientDrawable knob = new GradientDrawable();
        knob.setShape(GradientDrawable.OVAL);
        knob.setSize(dp(20), dp(20));
        knob.setColor(new ColorStateList(states, new int[]{c(0xFF6E6880), c(0xFFFFFFFF), c(0xFFE6E1F0)}));
        android.graphics.drawable.InsetDrawable thumb = new android.graphics.drawable.InsetDrawable(knob, dp(3));
        GradientDrawable track = new GradientDrawable();
        track.setSize(dp(52), dp(26));
        track.setCornerRadius(dp(13));
        track.setColor(new ColorStateList(states, new int[]{c(0x14FFFFFF), c(0xFF7C3AED), c(0x38FFFFFF)}));
        sw.setThumbDrawable(thumb);
        sw.setTrackDrawable(track);
        sw.setThumbTintList(null);
        sw.setTrackTintList(null);
        sw.setSwitchMinWidth(dp(52));
    }

    private String statusText(String pkg) {
        long now = System.currentTimeMillis();
        if (Core.mode(this, now) != null && Core.selected(this).contains(pkg)) return "Anchored: hidden from this phone";
        Long until = Core.scheduledNow(this, now).get(pkg);
        if (until != null) return "Hidden by its schedule until " + time(until, now);
        if (!schedulesFor(pkg).isEmpty()) return "Has a schedule";
        return "Not anchored";
    }

    private static String screenTime(long ms) {
        long minutes = ms / 60_000;
        if (ms <= 0) return "Not used";
        if (minutes < 1) return "Less than a minute";
        if (minutes < 60) return minutes + " min";
        return (minutes / 60) + " h" + (minutes % 60 > 0 ? " " + (minutes % 60) + " min" : "");
    }

    private String date(long ms) {
        return ms > 0 ? android.text.format.DateFormat.getMediumDateFormat(this).format(new java.util.Date(ms)) : "—";
    }

    private View fact(String name, String value) {
        LinearLayout row = new LinearLayout(this);
        row.setPadding(dp(14), dp(10), dp(14), dp(10));
        TextView n = text();
        n.setText(name);
        n.setTextColor(DIM);
        n.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        TextView v = text();
        v.setText(value);
        v.setTextColor(TEXT);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        v.setTextIsSelectable(true);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.addView(n);
        col.addView(v);
        row.addView(col);
        return row;
    }

    private LinearLayout twoLines(String top, String bottom, int topColor) {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        TextView t = text();
        t.setText(top);
        t.setTextColor(topColor);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        col.addView(t);
        if (!bottom.isEmpty()) {
            TextView b = text();
            b.setText(bottom);
            b.setTextColor(DIM);
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            col.addView(b);
        }
        return col;
    }

    private TextView groupTitle(String text) {
        TextView t = text();
        t.setText(text);
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        t.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        t.setPadding(dp(4), 0, 0, 0);
        return t;
    }

    private void confirm(String pkg, String heading, String message, String action, boolean danger,
                         final Runnable onAction) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();

        android.widget.FrameLayout badge = new android.widget.FrameLayout(this);
        GradientDrawable glow = new GradientDrawable();
        glow.setShape(GradientDrawable.OVAL);
        glow.setGradientType(GradientDrawable.RADIAL_GRADIENT);
        glow.setGradientRadius(dp(42));
        glow.setColors(new int[]{c(0x668B5CF6), c(0x008B5CF6)});
        badge.setBackground(glow);
        ImageView icon = new ImageView(this);
        Drawable d = appIcon(pkg);
        if (d != null) icon.setImageDrawable(d);
        android.widget.FrameLayout.LayoutParams iconLp = new android.widget.FrameLayout.LayoutParams(dp(56), dp(56));
        iconLp.gravity = Gravity.CENTER;
        badge.addView(icon, iconLp);
        box.addView(badge, new LinearLayout.LayoutParams(dp(84), dp(84)));

        box.addView(dialogHeading(heading), centered(dp(14)));
        box.addView(dialogText(message), centered(dp(8)));

        Button cancel = pillButton("Cancel", false);
        Button go = danger ? dangerButton(action) : pillButton(action, true);
        cancel.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        go.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
                onAction.run();
            }
        });
        box.addView(twoButtons(cancel, go), fill(dp(22)));
        showDialog(dialog, box);
    }

    private void showSchedules(final String pkg, final String name) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading(name + " schedule"), centered(0));
        box.addView(dialogText("Hide " + name + " at these times, even when nothing is anchored. This phone does it by "
                + "itself. Once added, a time can only be changed or removed on your computer."), centered(dp(8)));

        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setBackground(cardWithBorder(CARD, c(0x0FFFFFFF), dp(16)));
        for (Timing.Schedule sch : schedulesFor(pkg)) {
            list.addView(listRow("ic_alarm", daysText(sch), hoursText(sch) + (sch.enabled ? "" : " · Off")));
            list.addView(divider());
        }
        View add = listRow("ic_add", "Add a time", "");
        add.setClickable(true);
        add.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
                addTime(pkg, name);
            }
        });
        list.addView(add);
        box.addView(list, fill(dp(18)));

        Button done = pillButton("Done", false);
        done.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        box.addView(done, fill(dp(18)));
        showDialog(dialog, box);
    }

    private void addTime(final String pkg, final String name) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading("Add a time for " + name), centered(0));

        final boolean[] days = {false, true, true, true, true, true, true, true};
        LinearLayout dayRow = new LinearLayout(this);
        dayRow.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 1; i <= 7; i++) {
            final int day = i;
            final TextView chip = text();
            chip.setText(DAY_NAMES[i - 1]);
            chip.setGravity(Gravity.CENTER);
            chip.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            chip.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
            chip.setPadding(0, dp(9), 0, dp(9));
            styleDay(chip, true);
            chip.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    days[day] = !days[day];
                    styleDay(chip, days[day]);
                }
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
            lp.leftMargin = lp.rightMargin = dp(2);
            dayRow.addView(chip, lp);
        }
        box.addView(dayRow, fill(dp(18)));

        final int[] start = {22 * 60 + 30};
        final int[] end = {7 * 60};
        LinearLayout times = new LinearLayout(this);
        times.setOrientation(LinearLayout.HORIZONTAL);
        times.setGravity(Gravity.CENTER);
        times.addView(timeColumn("From", start));
        View gap = new View(this);
        times.addView(gap, new LinearLayout.LayoutParams(dp(28), 1));
        times.addView(timeColumn("To", end));
        box.addView(times, fill(dp(18)));

        TextView note = dialogText("If the end is earlier than the start, it ends the next morning. "
                + "The same start and end time means all day.");
        note.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        box.addView(note, centered(dp(14)));

        Button cancel = pillButton("Cancel", false);
        Button save = pillButton("Add", true);
        cancel.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        save.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                List<Integer> chosen = new ArrayList<>();
                for (int d = 1; d <= 7; d++) if (days[d]) chosen.add(d);
                if (chosen.isEmpty()) {
                    Toast.makeText(MainActivity.this, "Pick at least one day", Toast.LENGTH_SHORT).show();
                    return;
                }
                final int[] picked = new int[chosen.size()];
                for (int k = 0; k < picked.length; k++) picked[k] = chosen.get(k);
                dialog.dismiss();
                final Exception[] error = new Exception[1];
                inBackground(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            Core.addSchedule(MainActivity.this, pkg, name, picked, hhmm(start[0]), hhmm(end[0]));
                            Core.apply(MainActivity.this);
                        } catch (Exception e) {
                            error[0] = e;
                        }
                    }
                }, new Runnable() {
                    @Override
                    public void run() {
                        Toast.makeText(MainActivity.this, error[0] == null
                                ? name + ": " + daysText(picked) + " " + hoursText(start[0], end[0]) + " added"
                                : "Couldn't add the time: " + error[0].getMessage(),
                                error[0] == null ? Toast.LENGTH_SHORT : Toast.LENGTH_LONG).show();
                        refresh();
                    }
                });
            }
        });
        box.addView(twoButtons(cancel, save), fill(dp(22)));
        showDialog(dialog, box);
    }

    private View timeColumn(String caption, final int[] minutes) {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        TextView c = text();
        c.setText(caption);
        c.setTextColor(DIM);
        c.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        c.setTypeface(f(Typeface.DEFAULT_BOLD, true));
        col.addView(c);
        final TextView value = text();
        value.setText(hhmm(minutes[0]));
        value.setTextColor(TEXT);
        value.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        value.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        value.setPadding(dp(16), dp(6), dp(16), dp(6));
        value.setBackground(rounded(c(0x0DFFFFFF), dp(12)));
        value.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                new android.app.TimePickerDialog(MainActivity.this, new android.app.TimePickerDialog.OnTimeSetListener() {
                    @Override
                    public void onTimeSet(android.widget.TimePicker picker, int h, int m) {
                        minutes[0] = h * 60 + m;
                        value.setText(hhmm(minutes[0]));
                    }
                }, minutes[0] / 60, minutes[0] % 60, true).show();
            }
        });
        col.addView(value, wrap(dp(4)));
        return col;
    }

    private void styleDay(TextView chip, boolean on) {
        GradientDrawable bg = on
                ? new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{c(0xFF6A47B5), c(0xFF6A47B5)})
                : new GradientDrawable();
        if (!on) bg.setColor(c(0x14FFFFFF));
        bg.setCornerRadius(dp(12));
        chip.setBackground(bg);
        chip.setTextColor(on ? c(0xFFFFFFFF) : DIM);
    }

    private View listRow(String iconName, String titleText, String subtitle) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(12), dp(14), dp(12));
        row.addView(icon(iconName, ICON), new LinearLayout.LayoutParams(dp(20), dp(20)));
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        text.setPadding(dp(14), 0, 0, 0);
        TextView t = text();
        t.setText(titleText);
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        text.addView(t);
        if (!subtitle.isEmpty()) {
            TextView st = text();
            st.setText(subtitle);
            st.setTextColor(DIM);
            st.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            text.addView(st);
        }
        row.addView(text, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        return row;
    }

    private LinearLayout dialogBox() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setPadding(dp(24), dp(26), dp(24), dp(20));
        box.setBackground(cardWithBorder(c(0xFF1A1525), c(0x298B5CF6), dp(26)));
        return box;
    }

    private TextView dialogHeading(String text) {
        TextView heading = text();
        heading.setText(text);
        heading.setTextColor(TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        heading.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        heading.setGravity(Gravity.CENTER);
        return heading;
    }

    private TextView dialogText(String text) {
        TextView message = text();
        message.setText(text);
        message.setTextColor(DIM);
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        message.setLineSpacing(0, 1.25f);
        message.setGravity(Gravity.CENTER);
        return message;
    }

    private LinearLayout twoButtons(Button left, Button right) {
        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams half = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        half.rightMargin = dp(6);
        buttons.addView(left, half);
        LinearLayout.LayoutParams half2 = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        half2.leftMargin = dp(6);
        buttons.addView(right, half2);
        return buttons;
    }

    private void showDialog(android.app.Dialog dialog, View box) {
        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);
        dialog.setContentView(box);
        android.view.Window w = dialog.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT));
            w.setLayout(Math.min(getResources().getDisplayMetrics().widthPixels - dp(48), dp(380)),
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
            w.setDimAmount(0.7f);
        }
        dialog.show();
    }

    private void showFullScreen(android.app.Dialog dialog, View content, final View padded) {
        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);
        dialog.setContentView(content);
        android.view.Window w = dialog.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(BG));
            w.setLayout(android.view.ViewGroup.LayoutParams.MATCH_PARENT, android.view.ViewGroup.LayoutParams.MATCH_PARENT);
            w.setStatusBarColor(BG);
            w.setNavigationBarColor(BG);
        }
        padded.setPadding(dp(16), dp(28), dp(16), dp(24));

        content.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public android.view.WindowInsets onApplyWindowInsets(View v, android.view.WindowInsets insets) {
                int top, bottom;
                if (android.os.Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                    top = bars.top;
                    bottom = bars.bottom;
                } else {
                    top = insets.getSystemWindowInsetTop();
                    bottom = insets.getSystemWindowInsetBottom();
                }
                v.setPadding(0, top, 0, bottom);
                return insets;
            }
        });
        dialog.show();
    }

    private ImageView iconButton(String iconName, int color, boolean accent, String description, final Runnable onClick) {
        ImageView b = icon(iconName, color);
        b.setPadding(dp(9), dp(9), dp(9), dp(9));
        b.setContentDescription(description);
        if (accent) b.setBackground(rounded(c(0x298B5CF6), dp(99)));
        b.setClickable(true);
        if (onClick != null) {
            b.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    onClick.run();
                }
            });
        }
        return b;
    }

    private Button pillButton(String text, boolean primary) {
        Button b = button();
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        b.setTypeface(f(Typeface.create("sans-serif", Typeface.BOLD), true));
        b.setTextColor(primary ? c(0xFFFFFFFF) : c(0xFFE4DBFF));
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        b.setStateListAnimator(null);
        if (retro) {
            b.setTextColor(primary ? 0xFF000000 : TEXT);
            GradientDrawable themed = primary ? accentGradient() : rounded(BG, dp(9));
            themed.setCornerRadius(dp(9));
            themed.setStroke(stroke(), primary ? 0xFF000000 : c(0x0FFFFFFF));
            b.setBackground(themed);
            return b;
        }
        GradientDrawable bg;
        if (primary) {
            bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{c(0xFF6A47B5), c(0xFF6A47B5)});
        } else {
            bg = new GradientDrawable();
            bg.setColor(c(0x0AFFFFFF));
            bg.setStroke(dp(1), c(0xA6A78BFA));
        }
        bg.setCornerRadius(dp(99));
        b.setBackground(bg);
        return b;
    }

    private Button dangerButton(String text) {
        Button b = pillButton(text, false);
        b.setTextColor(c(0xFFFCA5A5));
        GradientDrawable bg = rounded(c(0x1FF87171), dp(99));
        bg.setStroke(dp(1), c(0x99F87171));
        b.setBackground(bg);
        return b;
    }

    private void anchorApp(final String pkg, final String name) {
        Set<String> selected = Core.selected(this);
        selected.add(pkg);
        Core.setSelected(this, selected);
        if (Core.mode(this, System.currentTimeMillis()) == null) Core.setShifted(this, true);
        refresh();
        final List<String>[] refused = new List[]{Collections.<String>emptyList()};
        inBackground(new Runnable() {
            @Override
            public void run() {
                refused[0] = Core.apply(MainActivity.this);
            }
        }, new Runnable() {
            @Override
            public void run() {
                Toast.makeText(MainActivity.this, refused[0].contains(pkg)
                        ? name + " can't be hidden (protected by Android)"
                        : name + " anchored · only your computer can release it", Toast.LENGTH_SHORT).show();
                refresh();
            }
        });
    }

    private void uninstallApp(final String pkg, final String name) {
        Toast.makeText(this, name + " is being uninstalled", Toast.LENGTH_SHORT).show();
        final RuntimeException[] error = new RuntimeException[1];
        inBackground(new Runnable() {
            @Override
            public void run() {
                try {
                    Core.uninstallApp(MainActivity.this, pkg);
                } catch (RuntimeException e) {
                    error[0] = e;
                }
            }
        }, new Runnable() {
            @Override
            public void run() {
                if (error[0] != null) {
                    Toast.makeText(MainActivity.this, "Couldn't uninstall " + name + ": " + error[0].getMessage(),
                            Toast.LENGTH_LONG).show();
                }

                lists.postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        refresh();
                    }
                }, 1500);
            }
        });
    }

    private boolean canUninstall(String pkg) {
        return Core.isInstalled(this, pkg) && !cameWithPhone(pkg) && !pkg.equals(getPackageName());
    }

    private boolean cameWithPhone(String pkg) {
        try {
            android.content.pm.ApplicationInfo ai = getPackageManager()
                    .getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES);
            return (ai.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private List<Timing.Schedule> schedulesFor(String pkg) {
        List<Timing.Schedule> out = new ArrayList<>();
        for (Timing.Schedule sch : Core.schedules(this)) if (sch.packages.contains(pkg)) out.add(sch);
        return out;
    }

    private String scheduleSummary(String pkg) {
        List<Timing.Schedule> list = schedulesFor(pkg);
        if (list.size() == 1) {
            Timing.Schedule sch = list.get(0);
            return daysText(sch) + " · " + hoursText(sch) + (sch.enabled ? "" : " · Off");
        }
        return count(list.size(), "schedule");
    }

    private static final String[] DAY_NAMES = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"};

    private static String daysText(Timing.Schedule sch) {
        List<Integer> d = new ArrayList<>();
        for (int i = 1; i <= 7; i++) if (sch.days[i]) d.add(i);
        int[] days = new int[d.size()];
        for (int i = 0; i < days.length; i++) days[i] = d.get(i);
        return daysText(days);
    }

    private static String daysText(int[] days) {
        StringBuilder key = new StringBuilder();
        for (int d : days) key.append(d);
        if (key.toString().equals("1234567")) return "Every day";
        if (key.toString().equals("12345")) return "Weekdays";
        if (key.toString().equals("67")) return "Weekends";
        StringBuilder out = new StringBuilder();
        for (int d : days) out.append(out.length() == 0 ? "" : ", ").append(DAY_NAMES[d - 1]);
        return out.toString();
    }

    private static String hoursText(Timing.Schedule sch) {
        return hoursText(sch.start, sch.end);
    }

    private static String hoursText(int start, int end) {
        return start == end ? "all day" : hhmm(start) + "–" + hhmm(end);
    }

    private static String hhmm(int minutes) {
        return String.format(java.util.Locale.ROOT, "%02d:%02d", minutes / 60, minutes % 60);
    }

    private void filter() {
        String q = search.getText().toString().trim().toLowerCase();
        java.util.Set<View> withMatches = new java.util.HashSet<>();
        for (View v : searchable) {
            boolean show = q.isEmpty() || String.valueOf(v.getTag()).contains(q);
            v.setVisibility(show ? View.VISIBLE : View.GONE);

            LinearLayout parent = (LinearLayout) v.getParent();
            int i = parent.indexOfChild(v);
            if (i > 0) parent.getChildAt(i - 1).setVisibility(show ? View.VISIBLE : View.GONE);
            if (show) withMatches.add(parent);
        }

        for (Object[] sec : sections) {
            View body = (View) sec[0];
            boolean open = q.isEmpty() ? openSections.contains((String) sec[2])
                    : withMatches.contains(body) || body.getVisibility() == View.VISIBLE;
            body.setVisibility(open ? View.VISIBLE : View.GONE);
            setIcon((ImageView) sec[1], open ? "ic_expand_more" : "ic_expand_less", GREY);
        }
    }

    private void setPill(String text, int color) {
        pill.setText(text);
        if (retro) {
            boolean active = color == VIOLET;
            pill.setTextColor(active ? 0xFF000000 : TEXT);
            GradientDrawable themed = active ? accentGradient() : rounded(BG, dp(99));
            themed.setCornerRadius(dp(99));
            themed.setStroke(stroke(), active ? 0xFF000000 : c(0x0FFFFFFF));
            pill.setBackground(themed);
            return;
        }
        pill.setTextColor(color);
        pill.setBackground(rounded(color == VIOLET ? c(0x478B5CF6) : c(0x14FFFFFF), dp(99)));
    }

    private ImageView icon(String name, int color) {
        ImageView v = new ImageView(this);
        setIcon(v, name, color);
        return v;
    }

    private void setIcon(ImageView v, String name, int color) {
        int id = getResources().getIdentifier(name, "drawable", getPackageName());
        if (id != 0) v.setImageDrawable(getDrawable(id));
        v.setImageTintList(ColorStateList.valueOf(color));
    }

    private View divider() {
        View d = new View(this);
        d.setBackgroundColor(c(0x0DFFFFFF));
        d.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Math.max(1, dp(1) / 2)));
        return d;
    }

    private GradientDrawable rounded(int color, int radius) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(radius);
        return g;
    }

    private GradientDrawable cardWithBorder(int color, int border, int radius) {
        GradientDrawable g = rounded(color, radius);
        g.setStroke(retro ? stroke() : Math.max(1, dp(1) / 2), border);
        return g;
    }

    private static void sortByName(List<String[]> rows) {
        Collections.sort(rows, new Comparator<String[]>() {
            @Override
            public int compare(String[] a, String[] b) {
                return a[1].compareToIgnoreCase(b[1]);
            }
        });
    }

    private String label(String pkg) {
        try {
            PackageManager pm = getPackageManager();
            return String.valueOf(pm.getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES).loadLabel(pm));
        } catch (PackageManager.NameNotFoundException e) {
            return pkg;
        }
    }

    private Drawable appIcon(String pkg) {
        try {
            PackageManager pm = getPackageManager();
            return pm.getApplicationInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES).loadIcon(pm);
        } catch (PackageManager.NameNotFoundException e) {
            return null;
        }
    }

    private static String count(int n, String word) {
        boolean upper = word.equals(word.toUpperCase());
        return n + " " + word + (n == 1 ? "" : upper ? "S" : "s");
    }

    private String time(long ms, long now) {
        java.util.Date d = new java.util.Date(ms);
        String t = android.text.format.DateFormat.getTimeFormat(this).format(d);
        return ms - now > 20 * 3600_000L ? t + " on " + android.text.format.DateFormat.getMediumDateFormat(this).format(d) : t;
    }

    private LinearLayout.LayoutParams fill(int topMargin) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = topMargin;
        return lp;
    }

    private LinearLayout.LayoutParams centered(int topMargin) {
        LinearLayout.LayoutParams lp = wrap(topMargin);
        lp.gravity = Gravity.CENTER_HORIZONTAL;
        return lp;
    }

    private LinearLayout.LayoutParams wrap(int topMargin) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = topMargin;
        return lp;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
