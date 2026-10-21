package app.anchor.agent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class AlarmReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Core.isOwner(context)) return;
        if (InstallBlocks.ACTION_CHECK.equals(intent.getAction())) InstallBlocks.check(context);
        else Core.apply(context);
    }
}
