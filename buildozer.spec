[app]
title = JawTracker Camera
package.name = jawtracker
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
requirements = python3,kivy==2.1.0,numpy,opencv-python==4.5.5.64,pillow,python-socketio==5.8.0
android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE
android.api = 30
android.minapi = 24
android.ndk = 28c
android.arch = arm64-v8a
android.sdk_path = /usr/local/android-sdk

[buildozer]
log_level = 2
