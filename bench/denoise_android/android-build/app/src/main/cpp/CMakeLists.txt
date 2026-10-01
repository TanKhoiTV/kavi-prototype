cmake_minimum_required(VERSION 3.22)
project("qnn_loader_jni")

# C++17 for std::vector etc.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Pre-compile the JNI bridge into libqnn_loader_jni.so.
# This is a thin wrapper that dlopen's libQnnHtp.so at runtime,
# so no link-time dependency on the QNN libraries.
add_library(
    qnn_loader_jni
    SHARED
    qnn_loader_jni.cpp
    gtcrn_denoise.cpp
    wiener_denoise.cpp
)

# Link against Android log library for __android_log_print
target_link_libraries(
    qnn_loader_jni
    log
    dl   # dlsym / dlopen
)