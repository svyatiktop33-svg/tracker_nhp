[app]
title = JawTracker Camera
package.name = jawtracker
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
requirements = python3,kivy==2.1.0,numpy
android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE
android.api = 30
android.minapi = 24
android.ndk = 28c
android.arch = arm64-v8a
android.accept_sdk_license = yes

[buildozer]
log_level = 2
