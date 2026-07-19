# ── AfriMine AI ProGuard Rules ────────────────────────────────────────────
# Optimized for minimal APK size on low-end Android devices.

# Flutter
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }
-keep class io.flutter.embedding.** { *; }

# Keep annotation defaults for Flutter plugins
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes InnerClasses,EnclosingMethod

# Dio (HTTP client)
-keep class com.squareup.okhttp3.** { *; }
-dontwarn com.squareup.okhttp3.**
-dontwarn okio.**
-keep class retrofit2.** { *; }
-dontwarn retrofit2.**

# SQLite / sqflite
-keep class org.sqlite.** { *; }
-keep class org.sqlite.database.** { *; }

# Camera plugin
-keep class androidx.camera.** { *; }

# Geolocator
-keep class com.baseflow.geolocator.** { *; }

# MapLibre
-keep class org.maplibre.** { *; }
-keep class com.mapbox.** { *; }
-dontwarn com.mapbox.**

# JSON serialization
-keep class com.afrimine.ai.** { *; }
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# General Android
-keepclassmembers class * extends java.lang.Enum {
    <fields>;
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# Remove logging in release
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}
