NAMES = {
    "CAMERA": "Camera",
    "RECORD_AUDIO": "Microphone",
    "ACCESS_FINE_LOCATION": "Precise location",
    "ACCESS_COARSE_LOCATION": "Approximate location",
    "ACCESS_BACKGROUND_LOCATION": "Location in the background",
    "ACCESS_MEDIA_LOCATION": "Location in photos",
    "READ_CONTACTS": "Contacts",
    "WRITE_CONTACTS": "Change contacts",
    "GET_ACCOUNTS": "Accounts on the phone",
    "POST_NOTIFICATIONS": "Notifications",
    "READ_MEDIA_IMAGES": "Photos",
    "READ_MEDIA_VIDEO": "Videos",
    "READ_MEDIA_AUDIO": "Music and audio",
    "READ_MEDIA_VISUAL_USER_SELECTED": "Selected photos and videos",
    "READ_EXTERNAL_STORAGE": "Files and media",
    "WRITE_EXTERNAL_STORAGE": "Change files and media",
    "READ_CALENDAR": "Calendar",
    "WRITE_CALENDAR": "Change calendar",
    "READ_PHONE_STATE": "Phone status",
    "READ_PHONE_NUMBERS": "Phone numbers",
    "CALL_PHONE": "Make calls",
    "ANSWER_PHONE_CALLS": "Answer calls",
    "READ_CALL_LOG": "Call history",
    "WRITE_CALL_LOG": "Change call history",
    "SEND_SMS": "Send text messages",
    "RECEIVE_SMS": "Receive text messages",
    "READ_SMS": "Read text messages",
    "BODY_SENSORS": "Body sensors",
    "ACTIVITY_RECOGNITION": "Physical activity",
    "BLUETOOTH_CONNECT": "Nearby devices (connect)",
    "BLUETOOTH_SCAN": "Nearby devices (scan)",
    "BLUETOOTH_ADVERTISE": "Nearby devices (be found)",
    "NEARBY_WIFI_DEVICES": "Nearby Wi-Fi devices",
    "UWB_RANGING": "Nearby device distance",
}

def friendly(permission, android_label=""):

    short = permission.rsplit(".", 1)[-1]
    title = NAMES.get(short) or short.replace("_", " ").capitalize()
    desc = android_label if android_label and android_label != permission else ""
    desc = desc[:1].upper() + desc[1:]
    return title, ("" if desc.casefold() == title.casefold() else desc)
