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
 * Never allow, Anchored apps and All other apps cards. Apps can be anchored, given a schedule or
 * uninstalled from here (all of which only block more), but never released, and a schedule can't be
 * changed or removed here: that only works from the paired computer.
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
            String note = schedulesFor(pkg).isEmpty() ? pkg : scheduleSummary(pkg);
            others.add(new String[]{pkg, String.valueOf(ri.activityInfo.applicationInfo.loadLabel(pm)), note});
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
            // Like the desktop: tapping an app shows its details and permissions.
            row.setBackground(new android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(0x228B5CF6), null,
                    new android.graphics.drawable.ColorDrawable(0xFFFFFFFF)));
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
        confirm(pkg, "Anchor " + name + "?",
                "It's hidden from this phone right away, and only your computer can bring it back.",
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

    /** An app's details and permissions, like the desktop's details window. */
    private void showDetails(final String pkg, final String name) {
        final org.json.JSONObject info;
        try {
            info = Permissions.info(this, pkg);
        } catch (Exception e) {
            Toast.makeText(this, "Couldn't read " + name + "'s details: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        // A full screen, not a floating card: a phone has less room than the desktop's window.
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
        about.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(16)));
        String[][] facts = {
                {"Status", statusText(pkg)},
                {"Version", info.optString("version").isEmpty() ? "—" : info.optString("version")},
                {"Installed", date(info.optLong("installed"))},
                {"Last updated", date(info.optLong("updated"))},
                {"Type", info.optBoolean("system") ? "Came with the phone" : "Installed by you"},
        };
        for (int i = 0; i < facts.length; i++) {
            if (i > 0) about.addView(divider());
            about.addView(fact(facts[i][0], facts[i][1]));
        }
        box.addView(about, fill(dp(8)));

        box.addView(groupTitle("Permissions"), fill(dp(20)));
        final LinearLayout perms = new LinearLayout(this);
        perms.setOrientation(LinearLayout.VERTICAL);
        final TextView permsNote = new TextView(this);
        permsNote.setTextColor(DIM);
        permsNote.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        permsNote.setLineSpacing(0, 1.2f);
        box.addView(permsNote, fill(dp(2)));
        box.addView(perms, fill(dp(8)));
        fillPermissions(perms, permsNote, pkg, name, info);

        if (canUninstall(pkg)) {  // apps you installed yourself, like the bin in the list
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

        Button done = pillButton("Done", false);
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

    /** One switch per permission; locked while the app is blocked, since its permissions are held back. */
    private void fillPermissions(final LinearLayout perms, TextView note, final String pkg, final String name,
                                 org.json.JSONObject info) {
        perms.removeAllViews();
        boolean blocked = info.optBoolean("blocked");
        note.setText(blocked
                ? "Permissions are removed while " + name + " is blocked, and come back when your computer releases it."
                : "Changes apply right away. You can still change them in the phone's Settings.");
        org.json.JSONArray list = info.optJSONArray("permissions");
        if (list == null || list.length() == 0) {
            perms.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(16)));
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
        perms.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(16)));
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
            int[][] states = {{-android.R.attr.state_enabled}, {android.R.attr.state_checked}, {}};
            sw.setThumbTintList(new ColorStateList(states, new int[]{0xFF5E5870, 0xFFF4F0FF, 0xFFF4F0FF}));
            sw.setTrackTintList(new ColorStateList(states, new int[]{0x14FFFFFF, 0xFF7C3AED, 0x1FFFFFFF}));
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
            // A fixed-width slot at the row's right edge, so every switch lines up in one column.
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

    /** Like the desktop's status line in the details window. */
    private String statusText(String pkg) {
        long now = System.currentTimeMillis();
        if (Core.mode(this, now) != null && Core.selected(this).contains(pkg)) return "Anchored: hidden from this phone";
        Long until = Core.scheduledNow(this, now).get(pkg);
        if (until != null) return "Hidden by its schedule until " + time(until, now);
        if (!schedulesFor(pkg).isEmpty()) return "Has a schedule";
        return "Not anchored";
    }

    private String date(long ms) {
        return ms > 0 ? android.text.format.DateFormat.getMediumDateFormat(this).format(new java.util.Date(ms)) : "—";
    }

    /** A property, like the desktop's: the name small and dim, the value below it. */
    private View fact(String name, String value) {
        LinearLayout row = new LinearLayout(this);
        row.setPadding(dp(14), dp(10), dp(14), dp(10));
        TextView n = new TextView(this);
        n.setText(name);
        n.setTextColor(DIM);
        n.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        TextView v = new TextView(this);
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
        TextView t = new TextView(this);
        t.setText(top);
        t.setTextColor(topColor);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        col.addView(t);
        if (!bottom.isEmpty()) {
            TextView b = new TextView(this);
            b.setText(bottom);
            b.setTextColor(DIM);
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            col.addView(b);
        }
        return col;
    }

    private TextView groupTitle(String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        t.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        t.setPadding(dp(4), 0, 0, 0);
        return t;
    }

    /** A question about one app: its icon on a soft violet glow, a heading, a sentence, Cancel and an action. */
    private void confirm(String pkg, String heading, String message, String action, boolean danger,
                         final Runnable onAction) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();

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

    /** An app's schedules: they can be looked at and added here, but changed or removed only on the computer. */
    private void showSchedules(final String pkg, final String name) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading(name + " schedule"), centered(0));
        box.addView(dialogText("Hide " + name + " at these times, even when nothing is anchored. This phone does it by "
                + "itself. Once added, a time can only be changed or removed on your computer."), centered(dp(8)));

        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setBackground(cardWithBorder(CARD, 0x0FFFFFFF, dp(16)));
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

    /** Days and a from/to time for a new schedule, like the desktop's "Add a time". */
    private void addTime(final String pkg, final String name) {
        final android.app.Dialog dialog = new android.app.Dialog(this);
        LinearLayout box = dialogBox();
        box.addView(dialogHeading("Add a time for " + name), centered(0));

        final boolean[] days = {false, true, true, true, true, true, true, true}; // 1 = Monday … 7 = Sunday
        LinearLayout dayRow = new LinearLayout(this);
        dayRow.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 1; i <= 7; i++) {
            final int day = i;
            final TextView chip = new TextView(this);
            chip.setText(DAY_NAMES[i - 1]);
            chip.setGravity(Gravity.CENTER);
            chip.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            chip.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
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
                int[] picked = new int[chosen.size()];
                for (int k = 0; k < picked.length; k++) picked[k] = chosen.get(k);
                try {
                    Core.addSchedule(MainActivity.this, pkg, name, picked, hhmm(start[0]), hhmm(end[0]));
                    Core.apply(MainActivity.this);
                    Toast.makeText(MainActivity.this, name + ": " + daysText(picked) + " "
                            + hoursText(start[0], end[0]) + " added", Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Couldn't add the time: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
                dialog.dismiss();
                refresh();
            }
        });
        box.addView(twoButtons(cancel, save), fill(dp(22)));
        showDialog(dialog, box);
    }

    /** "From" or "To" over a big time; tapping the time opens the phone's own time picker. */
    private View timeColumn(String caption, final int[] minutes) {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        TextView c = new TextView(this);
        c.setText(caption);
        c.setTextColor(DIM);
        c.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        c.setTypeface(Typeface.DEFAULT_BOLD);
        col.addView(c);
        final TextView value = new TextView(this);
        value.setText(hhmm(minutes[0]));
        value.setTextColor(TEXT);
        value.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        value.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        value.setPadding(dp(16), dp(6), dp(16), dp(6));
        value.setBackground(rounded(0x0DFFFFFF, dp(12)));
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
                ? new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{0xFF9B6DFF, 0xFF6D28D9})
                : new GradientDrawable();
        if (!on) bg.setColor(0x14FFFFFF);
        bg.setCornerRadius(dp(12));
        chip.setBackground(bg);
        chip.setTextColor(on ? 0xFFFFFFFF : DIM);
    }

    /** A row in a dialog's list: an icon, a title and an optional line under it. */
    private View listRow(String iconName, String titleText, String subtitle) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(12), dp(14), dp(12));
        row.addView(icon(iconName, ICON), new LinearLayout.LayoutParams(dp(20), dp(20)));
        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        text.setPadding(dp(14), 0, 0, 0);
        TextView t = new TextView(this);
        t.setText(titleText);
        t.setTextColor(TEXT);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        text.addView(t);
        if (!subtitle.isEmpty()) {
            TextView st = new TextView(this);
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
        box.setBackground(cardWithBorder(0xFF1A1525, 0x298B5CF6, dp(26)));
        return box;
    }

    private TextView dialogHeading(String text) {
        TextView heading = new TextView(this);
        heading.setText(text);
        heading.setTextColor(TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        heading.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        heading.setGravity(Gravity.CENTER);
        return heading;
    }

    private TextView dialogText(String text) {
        TextView message = new TextView(this);
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

    /** A dialog that fills the screen, with its content kept clear of the status and navigation bars. */
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
                padded.setPadding(dp(16), top + dp(28), dp(16), bottom + dp(24));
                return insets;
            }
        });
        dialog.show();
    }

    /** A round icon button: violet and tinted when it has something set (like a schedule). */
    private ImageView iconButton(String iconName, int color, boolean accent, String description, final Runnable onClick) {
        ImageView b = icon(iconName, color);
        b.setPadding(dp(9), dp(9), dp(9), dp(9));
        b.setContentDescription(description);
        if (accent) b.setBackground(rounded(0x298B5CF6, dp(99)));
        b.setClickable(true);
        b.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                onClick.run();
            }
        });
        return b;
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

    /** Red text on a red tint, like the desktop's Uninstall. */
    private Button dangerButton(String text) {
        Button b = pillButton(text, false);
        b.setTextColor(0xFFFCA5A5);
        GradientDrawable bg = rounded(0x1FF87171, dp(99));
        bg.setStroke(dp(1), 0x99F87171);
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

    /** Uninstalls an app the user chose here, the same way as from the computer. */
    private void uninstallApp(String pkg, String name) {
        try {
            Core.uninstallApp(this, pkg);
            Toast.makeText(this, name + " is being uninstalled", Toast.LENGTH_SHORT).show();
        } catch (RuntimeException e) {
            Toast.makeText(this, "Couldn't uninstall " + name + ": " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
        // Android uninstalls in the background: look again in a moment.
        lists.postDelayed(new Runnable() {
            @Override
            public void run() {
                refresh();
            }
        }, 1500);
    }

    /** Apps you installed yourself; apps that came with the phone can't be uninstalled. */
    private boolean canUninstall(String pkg) {
        try {
            android.content.pm.ApplicationInfo ai = getPackageManager().getApplicationInfo(pkg, 0);
            return (ai.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) == 0 && !pkg.equals(getPackageName());
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private List<Timing.Schedule> schedulesFor(String pkg) {
        List<Timing.Schedule> out = new ArrayList<>();
        for (Timing.Schedule sch : Core.schedules(this)) if (sch.packages.contains(pkg)) out.add(sch);
        return out;
    }

    /** Under an app's name, like the desktop: "Every day · 22:30–07:00", or "2 schedules". */
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

    /** "Every day", "Weekdays", "Weekends" or "Mon, Wed, Fri", like the desktop. */
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

    /** "22:30–07:00", or "all day" when start and end are the same. */
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
