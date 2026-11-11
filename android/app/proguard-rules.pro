# ONNX Runtime uses JNI
-keep class ai.onnxruntime.** { *; }
# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class com.edge.attendance.data.** { *** Companion; }
-keepclasseswithmembers class com.edge.attendance.data.** { kotlinx.serialization.KSerializer serializer(...); }
