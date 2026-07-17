# AfriMine AI ProGuard Rules

# Flutter
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Supabase
-keep class io.supabase.** { *; }

# Dio
-keep class io.flutter.plugins.connectivity.** { *; }

# Camera
-keep class io.flutter.plugins.camera.** { *; }

# Keep data models
-keep class com.afrimine.ai.models.** { *; }
