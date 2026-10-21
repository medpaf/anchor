package app.anchor.agent;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;

import java.io.FileInputStream;
import java.io.IOException;

public class Blackhole extends VpnService {
    private ParcelFileDescriptor tun;
    private Thread drain;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (tun == null) {
            start();
        }
        return START_STICKY;
    }

    private void start() {
        try {
            Builder b = new Builder()
                    .setSession("Anchor offline")
                    .addAddress("10.111.222.1", 32)
                    .addRoute("0.0.0.0", 0)
                    .setBlocking(true);
            try {
                b.addAddress("fd00:0:0:111::1", 128).addRoute("::", 0);
            } catch (RuntimeException ignored) {

            }
            tun = b.establish();
            if (tun == null) {
                return;
            }
            final FileInputStream in = new FileInputStream(tun.getFileDescriptor());
            drain = new Thread(new Runnable() {
                @Override
                public void run() {
                    byte[] buf = new byte[32767];
                    try {

                        while (!Thread.currentThread().isInterrupted() && in.read(buf) >= 0) {
                        }
                    } catch (IOException ignored) {
                    } finally {
                        try {
                            in.close();
                        } catch (IOException ignored) {
                        }
                    }
                }
            }, "anchor-blackhole");
            drain.start();
        } catch (RuntimeException e) {

        }
    }

    @Override
    public void onDestroy() {
        if (drain != null) {
            drain.interrupt();
            drain = null;
        }
        if (tun != null) {
            try {
                tun.close();
            } catch (IOException ignored) {
            }
            tun = null;
        }
        super.onDestroy();
    }
}
