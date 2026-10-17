package app.anchor.agent;

import android.app.Application;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;

/**
 * Notices new installs the moment they happen while Anchor's process is running, so a
 * never-allowed app is hidden before it can be opened. (When the process isn't running, the
 * once-a-minute check in {@link InstallBlocks} catches it.)
 */
public class AnchorApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_PACKAGE_ADDED);
        filter.addAction(Intent.ACTION_PACKAGE_REPLACED);
        filter.addAction(Intent.ACTION_PACKAGE_REMOVED);
        filter.addDataScheme("package");
        registerReceiver(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                InstallBlocks.check(context);
            }
        }, filter, Context.RECEIVER_NOT_EXPORTED);
    }
}
