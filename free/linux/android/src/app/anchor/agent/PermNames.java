package app.anchor.agent;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

final class PermNames {
    private static final Map<String, String> NAMES = new HashMap<>();

    static {
        String[][] names = {
                {"CAMERA", "Camera"},
                {"RECORD_AUDIO", "Microphone"},
                {"ACCESS_FINE_LOCATION", "Precise location"},
                {"ACCESS_COARSE_LOCATION", "Approximate location"},
                {"ACCESS_BACKGROUND_LOCATION", "Location in the background"},
                {"ACCESS_MEDIA_LOCATION", "Location in photos"},
                {"READ_CONTACTS", "Contacts"},
                {"WRITE_CONTACTS", "Change contacts"},
                {"GET_ACCOUNTS", "Accounts on the phone"},
                {"POST_NOTIFICATIONS", "Notifications"},
                {"READ_MEDIA_IMAGES", "Photos"},
                {"READ_MEDIA_VIDEO", "Videos"},
                {"READ_MEDIA_AUDIO", "Music and audio"},
                {"READ_MEDIA_VISUAL_USER_SELECTED", "Selected photos and videos"},
                {"READ_EXTERNAL_STORAGE", "Files and media"},
                {"WRITE_EXTERNAL_STORAGE", "Change files and media"},
                {"READ_CALENDAR", "Calendar"},
                {"WRITE_CALENDAR", "Change calendar"},
                {"READ_PHONE_STATE", "Phone status"},
                {"READ_PHONE_NUMBERS", "Phone numbers"},
                {"CALL_PHONE", "Make calls"},
                {"ANSWER_PHONE_CALLS", "Answer calls"},
                {"READ_CALL_LOG", "Call history"},
                {"WRITE_CALL_LOG", "Change call history"},
                {"SEND_SMS", "Send text messages"},
                {"RECEIVE_SMS", "Receive text messages"},
                {"READ_SMS", "Read text messages"},
                {"BODY_SENSORS", "Body sensors"},
                {"ACTIVITY_RECOGNITION", "Physical activity"},
                {"BLUETOOTH_CONNECT", "Nearby devices (connect)"},
                {"BLUETOOTH_SCAN", "Nearby devices (scan)"},
                {"BLUETOOTH_ADVERTISE", "Nearby devices (be found)"},
                {"NEARBY_WIFI_DEVICES", "Nearby Wi-Fi devices"},
                {"UWB_RANGING", "Nearby device distance"},
        };
        for (String[] n : names) NAMES.put(n[0], n[1]);
    }

    private PermNames() {
    }

    static String[] friendly(String permission, String androidLabel) {
        String shortName = permission.substring(permission.lastIndexOf('.') + 1);
        String title = NAMES.get(shortName);
        if (title == null) {
            String words = shortName.replace('_', ' ').toLowerCase(Locale.ROOT);
            title = words.isEmpty() ? permission : Character.toUpperCase(words.charAt(0)) + words.substring(1);
        }
        String desc = androidLabel != null && !androidLabel.equals(permission) ? androidLabel : "";
        if (!desc.isEmpty()) desc = Character.toUpperCase(desc.charAt(0)) + desc.substring(1);
        return new String[]{title, desc.equalsIgnoreCase(title) ? "" : desc};
    }
}
