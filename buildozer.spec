[app]
title = JawTracker Camera
package.name = jawtracker
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
requirements = python3,kivy==2.1.0,numpy,opencv,requests
android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE
android.api = 30
android.minapi = 24
android.ndk = 28c
android.arch = arm64-v8a
android.accept_sdk_license = yes
android.build_options = -j 1

[buildozer]
log_level = 2
