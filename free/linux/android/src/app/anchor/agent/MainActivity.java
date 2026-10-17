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
import android.text.TextUtils;
import android.text.TextWatcher;
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

/**
 * The phone's Anchor screen, laid out like the desktop app: a status card, a search box, and the
 * Never allow, Anchored apps and All other apps cards. Apps can be anchored from here (blocking is
 * always allowed) but never released: that only works from the paired computer.
 */
public class MainActivity extends Activity {
    // Same palette as the desktop app.
    private static final int BG = 0xFF0D0A14;
    private static final int CARD = 0xFF16121F;
    private static final int TEXT = 0xFFEEEAF7;
    private static final int DIM = 0x99EEEAF7;
    private static final int ICON = 0xFFC4B5FD;
    private static final int VIOLET = 0xFFB39DFF;
    private static final int GREY = 0xFF9A93AD;

    private TextView pill;
    private TextView title;
    private TextView detail;
    private EditText search;
    private LinearLayout lists;
    /** Every app row (its search text is in its tag), so the search box can filter them. */
    private final List<View> searchable = new ArrayList<>();
    /** Each list's body (the part that folds), with how the user left it: folded or open. */
    private final List<Object[]> sections = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (getActionBar() != null) getActionBar().hide();
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setBackgroundColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setBackgroundColor(BG);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(16), dp(40), dp(16), dp(32));

        ImageView icon = new ImageView(this);
        // Just the orb (the icon's foreground layer), like the emblem in the desktop app.
        int orb = getResources().getIdentifier("ic_fg", "drawable", getPackageName());
        icon.setImageDrawable(orb != 0 ? getDrawable(orb) : getApplicationInfo().loadIcon(getPackageManager()));
        root.addView(icon, new LinearLayout.LayoutParams(dp(132), dp(132)));

        pill = new TextView(this);
        pill.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        pill.setTypeface(Typeface.DEFAULT_BOLD);
        pill.setAllCaps(true);
        pill.setLetterSpacing(0.14f);
        pill.setPadding(dp(14), dp(6), dp(14), dp(6));
        root.addView(pill, centered(dp(28)));

        title = new TextView(this);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 32);
        title.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        title.setTextColor(TEXT);
        title.setLetterSpacing(-0.01f);
        title.setGravity(Gravity.CENTER);
        root.addView(title, centered(dp(14)));

        detail = new TextView(this);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        detail.setGravity(Gravity.CENTER);
        detail.setLineSpacing(0, 1.3f);
        detail.setTextColor(DIM);
        LinearLayout.LayoutParams dlp = centered(dp(12));
        dlp.leftMargin = dlp.rightMargin = dp(8);
        root.addView(detail, dlp);

        // The search bar (added above the lists below).
        search = new EditText(this);
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

        // Search bar above the lists, like the desktop; it filters every list.
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.HORIZONTAL);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setPadding(dp(14), 0, dp(14), 0);
        box.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(14)));
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
        // Android 15+ draws apps edge to edge, under the status bar: keep the content clear of the
        // status bar at the top and the navigation bar at the bottom.
        final LinearLayout content = root;
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
                content.setPadding(dp(16), top + dp(28), dp(16), bottom + dp(32));
                return insets;
            }
        });
        setContentView(scroll);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh();
    }

    private void refresh() {
        boolean ready = Core.isOwner(this) && Core.isPaired(this);
        long now = System.currentTimeMillis();
        String mode = Core.mode(this, now);
        long ends = Core.shiftEnds(this, now);

        // Anchored: the anchored list (while anchored) and apps hidden by their schedule right now.
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

        // Status, as before: pill, title and a sentence.
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
        if (!ready) return;

        // Never allow (no icons, like the desktop): the package name, unless there's something to explain.
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

        // All other apps: everything that could be anchored from here.
        List<String[]> others = new ArrayList<>();
        PackageManager pm = getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        Set<String> seen = new TreeSet<>();
        for (ResolveInfo ri : pm.queryIntentActivities(launcher, 0)) {
            String pkg = ri.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || anchored.containsKey(pkg) || !seen.add(pkg)) continue;
            others.add(new String[]{pkg, String.valueOf(ri.activityInfo.applicationInfo.loadLabel(pm)), pkg});
        }
        sortByName(others);

        addSection("Never allow", "Apps that can't be installed.", "ic_block", never, false, false);
        if (!hidden.isEmpty()) {
            addSection("Anchored apps", "Hidden from this phone. Only your computer can release them.",
                    "ic_anchor", hidden, true, false);
        }
        addSection(hidden.isEmpty() ? "Your apps" : "All other apps",
                "Tap Anchor to hide an app from this phone right away.", "ic_grid", others, true, true);
        filter();
    }

    /** A card like the desktop's: a header row (logo, title, hint, chevron) with the apps below it. */
    private void addSection(String name, String hint, String logo, List<String[]> rows,
                            boolean icons, boolean anchorButtons) {
        final SharedPreferences ui = getSharedPreferences("anchor_ui", MODE_PRIVATE);
        final String key = "folded_" + logo;

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(18)));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(16), dp(12), dp(16), dp(12));
        header.setClickable(true);
        header.addView(icon(logo, ICON), new LinearLayout.LayoutParams(dp(20), dp(20)));
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        text.setPadding(dp(14), 0, dp(8), 0);
        TextView t = new TextView(this);
        t.setText(name + " (" + rows.size() + ")");
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        text.addView(t);
        TextView h = new TextView(this);
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

        boolean folded = ui.getBoolean(key, false);
        body.setVisibility(folded ? View.GONE : View.VISIBLE);
        // Same as the desktop: down while open, up while folded.
        setIcon(chevron, folded ? "ic_expand_less" : "ic_expand_more", GREY);
        header.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                boolean nowFolded = body.getVisibility() == View.VISIBLE;
                body.setVisibility(nowFolded ? View.GONE : View.VISIBLE);
                setIcon(chevron, nowFolded ? "ic_expand_less" : "ic_expand_more", GREY);
                ui.edit().putBoolean(key, nowFolded).apply();
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
            ImageView icon = new ImageView(this);
            Drawable d = appIcon(pkg);
            if (d != null) icon.setImageDrawable(d);
            LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(dp(36), dp(36));
            ip.rightMargin = dp(12);
            row.addView(icon, ip);
        }
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        TextView label = new TextView(this);
        label.setText(name);
        label.setTextColor(TEXT);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        label.setSingleLine(true);
        label.setEllipsize(TextUtils.TruncateAt.END);
        text.addView(label);
        if (!note.isEmpty()) {
            TextView n = new TextView(this);
            n.setText(note);
            n.setTextColor(DIM);
            n.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            n.setSingleLine(true);
            n.setEllipsize(TextUtils.TruncateAt.MIDDLE);
            text.addView(n);
        }
        row.addView(text, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        if (anchorButton) {
            Button anchor = new Button(this);
            anchor.setText("Anchor");
            anchor.setAllCaps(false);
            anchor.setTextColor(0xFFFFFFFF);
            anchor.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            anchor.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
            anchor.setMinHeight(0);
            anchor.setMinimumHeight(0);
            anchor.setMinWidth(0);
            anchor.setMinimumWidth(0);
            anchor.setPadding(dp(18), dp(8), dp(18), dp(8));
            GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                    new int[]{0xFF9B6DFF, 0xFF6D28D9});
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

    /** Asks first, in Anchor's own style: anchoring from the phone can't be undone from the phone. */
    private void confirmAnchor(final String pkg, final String name) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setPadding(dp(24), dp(26), dp(24), dp(20));
        box.setBackground(cardWithBorder(0xFF1A1525, 0x298B5CF6, dp(26)));

        // The app's icon on a soft violet glow, like the anchor emblem.
        android.widget.FrameLayout badge = new android.widget.FrameLayout(this);
        GradientDrawable glow = new GradientDrawable();
        glow.setShape(GradientDrawable.OVAL);
        glow.setGradientType(GradientDrawable.RADIAL_GRADIENT);
        glow.setGradientRadius(dp(42));
        glow.setColors(new int[]{0x668B5CF6, 0x008B5CF6});
        badge.setBackground(glow);
        ImageView icon = new ImageView(this);
        Drawable d = appIcon(pkg);
        if (d != null) icon.setImageDrawable(d);
        android.widget.FrameLayout.LayoutParams iconLp = new android.widget.FrameLayout.LayoutParams(dp(56), dp(56));
        iconLp.gravity = Gravity.CENTER;
        badge.addView(icon, iconLp);
        box.addView(badge, new LinearLayout.LayoutParams(dp(84), dp(84)));

        TextView heading = new TextView(this);
        heading.setText("Anchor " + name + "?");
        heading.setTextColor(TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        heading.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        heading.setGravity(Gravity.CENTER);
        box.addView(heading, centered(dp(14)));

        TextView message = new TextView(this);
        message.setText("It's hidden from this phone right away, and only your computer can bring it back.");
        message.setTextColor(DIM);
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        message.setLineSpacing(0, 1.25f);
        message.setGravity(Gravity.CENTER);
        box.addView(message, centered(dp(8)));

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button cancel = pillButton("Cancel", false);
        cancel.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
            }
        });
        Button anchor = pillButton("Anchor", true);
        anchor.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
                anchorApp(pkg, name);
            }
        });
        LinearLayout.LayoutParams half = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        half.rightMargin = dp(6);
        buttons.addView(cancel, half);
        LinearLayout.LayoutParams half2 = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        half2.leftMargin = dp(6);
        buttons.addView(anchor, half2);
        box.addView(buttons, fill(dp(22)));

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

    /** Violet gradient pill (main action) or a quiet outlined pill, like the desktop buttons. */
    private Button pillButton(String text, boolean primary) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        b.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        b.setTextColor(primary ? 0xFFFFFFFF : 0xFFE4DBFF);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        b.setStateListAnimator(null);
        GradientDrawable bg;
        if (primary) {
            bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{0xFF9B6DFF, 0xFF6D28D9});
        } else {
            bg = new GradientDrawable();
            bg.setColor(0x0AFFFFFF);
            bg.setStroke(dp(1), 0xA6A78BFA);
        }
        bg.setCornerRadius(dp(99));
        b.setBackground(bg);
        return b;
    }

    /** Anchors one app from the phone: blocking is always allowed here, releasing never is. */
    private void anchorApp(String pkg, String name) {
        Set<String> selected = Core.selected(this);
        selected.add(pkg);
        Core.setSelected(this, selected);
        if (Core.mode(this, System.currentTimeMillis()) == null) Core.setShifted(this, true);
        List<String> refused = Core.apply(this);
        Toast.makeText(this, refused.contains(pkg)
                ? name + " can't be hidden (protected by Android)"
                : name + " anchored · only your computer can release it", Toast.LENGTH_SHORT).show();
        refresh();
    }

    private void filter() {
        String q = search.getText().toString().trim().toLowerCase();
        java.util.Set<View> withMatches = new java.util.HashSet<>();
        for (View v : searchable) {
            boolean show = q.isEmpty() || String.valueOf(v.getTag()).contains(q);
            v.setVisibility(show ? View.VISIBLE : View.GONE);
            // The divider above each row goes with it.
            LinearLayout parent = (LinearLayout) v.getParent();
            int i = parent.indexOfChild(v);
            if (i > 0) parent.getChildAt(i - 1).setVisibility(show ? View.VISIBLE : View.GONE);
            if (show) withMatches.add(parent);
        }
        // Like the desktop: while searching, open the lists that have matches. When the search is
        // cleared, each list goes back to how the user left it.
        SharedPreferences ui = getSharedPreferences("anchor_ui", MODE_PRIVATE);
        for (Object[] sec : sections) {
            View body = (View) sec[0];
            boolean open = q.isEmpty() ? !ui.getBoolean((String) sec[2], false)
                    : withMatches.contains(body) || body.getVisibility() == View.VISIBLE;
            body.setVisibility(open ? View.VISIBLE : View.GONE);
            setIcon((ImageView) sec[1], open ? "ic_expand_more" : "ic_expand_less", GREY);
        }
    }

    // ---- Small helpers ----------------------------------------------------------------------

    private void setPill(String text, int color) {
        pill.setText(text);
        pill.setTextColor(color);
        pill.setBackground(rounded(color == VIOLET ? 0x478B5CF6 : 0x14FFFFFF, dp(99)));
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
        d.setBackgroundColor(0x0DFFFFFF);
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
        g.setStroke(Math.max(1, dp(1) / 2), border);
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

    /** "1 app", "13 apps", "13 APPS". */
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
