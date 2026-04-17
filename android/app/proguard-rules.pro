# Add project specific ProGuard rules here.

# Keep data model classes (used with Gson serialization)
-keep class com.communionafterdark.cad.data.model.** { *; }

# Keep API interface and result classes
-keep class com.communionafterdark.cad.data.api.** { *; }

# Keep Retrofit interfaces
-keepattributes Signature
-keepattributes *Annotation*
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}

# OkHttp / Okio
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**

# Gson
-keepattributes *Annotation*
-dontwarn sun.misc.**
-keep class com.google.gson.** { *; }
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer

# Media3
-keep class androidx.media3.** { *; }

# Compose
-keep class androidx.compose.** { *; }
