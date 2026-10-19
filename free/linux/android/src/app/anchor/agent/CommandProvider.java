package app.anchor.agent;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.Binder;
import android.os.Build;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.os.Process;
import android.provider.Settings;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * The desktop app talks to the phone through this provider over adb:
 *
 * <pre>
 *   adb shell content call --uri content://app.anchor.agent.cmd --method shift --arg BASE64_JSON
 *   adb exec-out content read --uri content://app.anchor.agent.cmd/apps.zip
 * </pre>
 *
 * Calls are only accepted from the adb shell (or root), never from other apps on the phone, and
 * every command that changes anything must carry the computer's key.
 */
public class CommandProvider extends ContentProvider {
    static final int VERSION = 42;
    private static final int SHELL_UID = 2000;
    private static final int ICON_PX = 96;

    @Override
    public boolean onCreate() {
        return true;
    }

    private static void requireAdb() {
        int uid = Binder.getCallingUid();
        if (uid != SHELL_UID && uid != Process.ROOT_UID) {
            throw new SecurityException("Anchor only accepts commands over USB from its desktop app");
        }
    }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        requireAdb();
        JSONObject out;
        try {
            JSONObject in = arg == null || arg.isEmpty()
                    ? new JSONObject()
                    : new JSONObject(new String(Base64.decode(arg, Base64.DEFAULT), StandardCharsets.UTF_8));
            out = handle(getContext(), method, in);
            out.put("ok", true);
        } catch (AgentError e) {
            out = error(e.code, e.getMessage());
        } catch (JSONException | IllegalArgumentException | NullPointerException e) {
            out = error("bad_request", e.getMessage());
        } catch (RuntimeException e) {
            out = error("internal", e.toString());
        }
        Bundle b = new Bundle();
        b.putString("json", out.toString());
        return b;
    }

    private static JSONObject error(String code, String message) {
        JSONObject o = new JSONObject();
        try {
            o.put("ok", false).put("error", code).put("message", message);
        } catch (JSONException ignored) {
        }
        return o;
    }

    private JSONObject handle(Context c, String method, JSONObject in) throws JSONException, AgentError {
        String token = in.optString("token", "");
        switch (method) {
            case "status":
                // {"edition": "free" | "pro"}: which desktop app is asking (see Edition).
                Edition.remember(c, in.optString("edition", ""));
                return status(c, token);
            case "pair":
                requireOwner(c);
                if (Core.isPaired(c)) throw new AgentError("already_paired", "This phone is already paired with a computer");
                if (token.length() < 16) throw new AgentError("bad_request", "Key too short");
                Core.pair(c, token);
                return status(c, token);
            case "select":
                requireAuth(c, token);
                Core.setSelected(c, strings(in.getJSONArray("packages")));
                Core.apply(c);
                return status(c, token);
            case "shift":
                // {"minutes": N} for a timed shift; without it the shift lasts until unshifted.
                requireAuth(c, token);
                if (in.has("packages")) Core.setSelected(c, strings(in.getJSONArray("packages")));
                if (in.has("minutes")) Core.shiftFor(c, in.getInt("minutes"));
                else Core.setShifted(c, true);
                Core.apply(c);
                return status(c, token);
            case "app_info":
                // {"pkg": ...}: details and permissions for the computer's details window.
                requireOwner(c);
                return Permissions.info(c, in.getString("pkg"));
            case "set_permission":
                // {"pkg", "permission", "grant": true/false}
                requireAuth(c, token);
                Permissions.set(c, in.getString("pkg"), in.getString("permission"), in.getBoolean("grant"));
                return Permissions.info(c, in.getString("pkg"));
            case "end":
                // The last anchored app was released: stop anchoring, leave schedules alone.
                requireAuth(c, token);
                Core.endShift(c);
                Core.apply(c);
                return status(c, token);
            case "uninstall":
                // {"pkg": ...}: the user clicked Uninstall on the computer.
                requireAuth(c, token);
                Core.uninstallApp(c, in.getString("pkg"));
                return status(c, token);
            case "unshift":
                requireAuth(c, token);
                Core.unshift(c);
                Core.apply(c);
                return status(c, token);
            case "schedules":
                requireAuth(c, token);
                Core.setSchedules(c, in.getJSONArray("schedules"));
                Core.apply(c);
                return status(c, token);
            case "install_blocks":
                // {"apps": [{"pkg": "com.instagram.android", "name": "Instagram"}, ...]}: the full list.
                requireAuth(c, token);
                InstallBlocks.set(c, in.getJSONArray("apps"));
                Core.apply(c);
                return status(c, token);
            case "check":
                // Re-apply right away (e.g. after the computer installed a placeholder). Harmless:
                // it can only enforce blocks, never lift them, so it needs no key.
                requireOwner(c);
                InstallBlocks.check(c);
                return status(c, token);
            case "uninstall_blocked":
                // {"pkg": ...}: the user asked to remove a blocked app that got installed.
                requireAuth(c, token);
                InstallBlocks.uninstallCaught(c, in.getString("pkg"));
                return status(c, token);
            case "private_dns_unlock":
                // Pro: just before the computer writes the phone's Private DNS setting over USB.
                requireAuth(c, token);
                PrivateDns.unlock(c);
                return status(c, token);
            case "private_dns_lock":
                // Pro: {"host": "family.cloudflare-dns.com"} once written, or {"host": null} for the
                // phone's own setting (unlocked).
                requireAuth(c, token);
                PrivateDns.lock(c, in.isNull("host") ? null : in.getString("host"));
                return status(c, token);
            case "restore_system_app":
                // {"pkg": ...}: brings back an app that came with the phone and was uninstalled.
                // Only the computer can: the phone app never offers it.
                requireAuth(c, token);
                SystemApps.restore(c, in.getString("pkg"));
                Core.apply(c);
                return status(c, token);
            case "factory_reset_lock":
                // Pro: {"locked": true} greys out "Erase all data" in the phone's Settings. Recovery mode
                // (the phone's buttons at start-up) can't be blocked by any app and still works.
                requireAuth(c, token);
                Core.lockFactoryReset(c, in.getBoolean("locked"));
                return status(c, token);
            case "release":
                requireAuth(c, token);
                Core.release(c);
                return status(c, token);
            default:
                throw new AgentError("unknown_method", "Unknown command: " + method);
        }
    }

    private static void requireOwner(Context c) throws AgentError {
        if (!Core.isOwner(c)) throw new AgentError("not_owner", "Anchor isn't the device owner yet");
    }

    private static void requireAuth(Context c, String token) throws AgentError {
        requireOwner(c);
        if (!Core.checkToken(c, token)) throw new AgentError("bad_key", "This computer's key doesn't match the phone");
    }

    private static JSONObject status(Context c, String token) throws JSONException {
        long now = System.currentTimeMillis();
        String mode = Core.mode(c, now);
        return new JSONObject()
                .put("now", now)
                .put("mode", mode == null ? JSONObject.NULL : mode)
                .put("ends", Core.shiftEnds(c, now))
                .put("scheduled_now", new JSONObject(Core.scheduledNow(c, now)))
                .put("paused", new JSONObject(Core.paused(c, now)))
                .put("schedules", Core.schedulesJson(c))
                .put("install_blocks", InstallBlocks.list(c))
                .put("install_blocks_set", InstallBlocks.isSet(c))
                .put("install_kept", new JSONArray(InstallBlocks.kept(c)))
                .put("install_caught", new JSONArray(InstallBlocks.caught(c)))
                .put("install_placeholders", new JSONArray(InstallBlocks.placeholders(c)))
                .put("install_missing", new JSONArray(InstallBlocks.missing(c)))
                .put("permissions_removed", new JSONObject(Permissions.counts(c)))
                .put("private_dns", PrivateDns.status(c))
                .put("factory_reset_locked", Core.factoryResetLocked(c))
                .put("removed_system", SystemApps.removed(c))
                .put("core_apps", SystemApps.core(c))
                .put("edition", Edition.get(c))
                .put("exact_alarms", Core.canWakeExactly(c))
                .put("version", VERSION)
                .put("model", Build.MANUFACTURER + " " + Build.MODEL)
                .put("android", Build.VERSION.RELEASE)
                // Free version: lets the computer stay with one phone. Changes only on a factory reset.
                .put("device_id", Settings.Secure.getString(c.getContentResolver(), Settings.Secure.ANDROID_ID))
                .put("owner", Core.isOwner(c))
                .put("paired", Core.isPaired(c))
                .put("authorized", Core.checkToken(c, token))
                .put("shifted", mode != null)
                .put("shifted_at", Core.shiftedAt(c))
                .put("selected", new JSONArray(Core.selected(c)))
                .put("blocked", new JSONArray(visibleBlocked(c)))
                .put("failed", new JSONArray(Core.failed(c)));
    }

    /** Hidden apps, leaving out Anchor's own placeholders (they're reported separately). */
    private static Set<String> visibleBlocked(Context c) {
        Set<String> out = new java.util.TreeSet<>(Core.blocked(c));
        out.removeAll(InstallBlocks.placeholders(c));
        return out;
    }

    private static List<String> strings(JSONArray a) throws JSONException {
        List<String> l = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) l.add(a.getString(i));
        return l;
    }

    // ---- App list (apps.json + icons/<package>.png in a zip, streamed over a pipe) ---------

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        requireAdb();
        if (!"apps.zip".equals(uri.getLastPathSegment())) throw new FileNotFoundException(uri.toString());
        final ParcelFileDescriptor[] pipe;
        try {
            pipe = ParcelFileDescriptor.createPipe();
        } catch (IOException e) {
            throw new FileNotFoundException(e.toString());
        }
        final Context c = getContext();
        new Thread(new Runnable() {
            @Override
            public void run() {
                try (OutputStream os = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) {
                    writeApps(c, os);
                } catch (IOException | JSONException ignored) {
                    // Reader went away; nothing to do.
                }
            }
        }, "anchor-apps").start();
        return pipe[0];
    }

    private static void writeApps(Context c, OutputStream os) throws IOException, JSONException {
        PackageManager pm = c.getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        Map<String, ApplicationInfo> apps = new TreeMap<>();
        for (ResolveInfo ri : pm.queryIntentActivities(launcher, PackageManager.MATCH_DISABLED_COMPONENTS)) {
            ApplicationInfo ai = ri.activityInfo.applicationInfo;
            if (!ai.packageName.equals(c.getPackageName())) apps.put(ai.packageName, ai);
        }
        // Hidden (blocked) apps have no launcher entry; keep every selected app listed.
        addInstalled(c, pm, apps, Core.selected(c));

        ZipOutputStream zip = new ZipOutputStream(os);
        JSONArray list = new JSONArray();
        for (ApplicationInfo ai : apps.values()) {
            list.put(new JSONObject()
                    .put("pkg", ai.packageName)
                    .put("label", String.valueOf(ai.loadLabel(pm)))
                    .put("system", (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0));
            try {
                Bitmap bmp = toBitmap(ai.loadIcon(pm));
                zip.putNextEntry(new ZipEntry("icons/" + ai.packageName + ".png"));
                bmp.compress(Bitmap.CompressFormat.PNG, 100, zip);
                zip.closeEntry();
            } catch (RuntimeException ignored) {
                // Missing icon is fine.
            }
        }
        zip.putNextEntry(new ZipEntry("apps.json"));
        zip.write(new JSONObject().put("apps", list).toString().getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
        zip.finish();
        zip.flush();
    }

    private static void addInstalled(Context c, PackageManager pm, Map<String, ApplicationInfo> apps, Collection<String> pkgs) {
        for (String p : pkgs) {
            if (apps.containsKey(p) || p.equals(c.getPackageName())) continue;
            try {
                ApplicationInfo ai = pm.getApplicationInfo(p, PackageManager.MATCH_UNINSTALLED_PACKAGES);
                if ((ai.flags & ApplicationInfo.FLAG_INSTALLED) != 0) apps.put(p, ai);
            } catch (PackageManager.NameNotFoundException ignored) {
            }
        }
    }

    private static Bitmap toBitmap(Drawable d) {
        Bitmap b = Bitmap.createBitmap(ICON_PX, ICON_PX, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(b);
        d.setBounds(0, 0, ICON_PX, ICON_PX);
        d.draw(canvas);
        return b;
    }

    // ---- Unused ContentProvider surface ---------------------------------------------------

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }

    static final class AgentError extends Exception {
        final String code;

        AgentError(String code, String message) {
            super(message);
            this.code = code;
        }
    }
}
