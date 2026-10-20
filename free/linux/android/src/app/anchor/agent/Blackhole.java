package app.anchor.agent;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;

import java.io.FileInputStream;
import java.io.IOException;

/**
 * Offline mode: a VPN that captures every packet and forwards nothing, so no app on the phone can
 * reach the internet over any transport (Wi-Fi, cellular or anything else).
 *
 * <p>The desktop turns this on by making Anchor the phone's locked always-on VPN (a device-owner
 * power, so there's no consent prompt). "Locked" means the system drops all traffic whenever the
 * tunnel isn't up, so this fails closed even if {@link #establish} is refused.
 *
 * <p>It opens no sockets and never talks to the network — it only reads the local tunnel and throws
 * the packets away — so Anchor still needs no internet permission.
 */
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
                // Some phones refuse IPv6 on the tunnel; IPv4 alone plus lockdown still blocks it.
            }
            tun = b.establish();
            if (tun == null) {
                return; // Consent revoked: lockdown always-on still blocks all traffic.
            }
            final FileInputStream in = new FileInputStream(tun.getFileDescriptor());
            drain = new Thread(new Runnable() {
                @Override
                public void run() {
                    byte[] buf = new byte[32767];
                    try {
                        // Read and discard forever: nothing is written back, so nothing leaves the phone.
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
            // establish() refused; lockdown keeps the phone offline anyway.
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
