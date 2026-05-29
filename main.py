#!/usr/bin/env python3
"""
JawTracker Mobile Light – Передача кадров на сервер
Минимальные зависимости, гарантированная сборка.
"""
import requests
import cv2
import numpy as np
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.image import Image
import time
import threading

class NetworkSender:
    def __init__(self, server_url):
        self.server_url = server_url
        self.session = requests.Session()

    def send_frame(self, jpg_bytes, camera_id):
        try:
            files = {'frame': ('frame.jpg', jpg_bytes, 'image/jpeg')}
            data = {'camera_id': camera_id}
            self.session.post(f"{self.server_url}/upload_frame", files=files, data=data, timeout=1)
        except:
            pass

class JawTrackerApp(App):
    def build(self):
        self.server_url = "http://192.168.1.100:5000"
        self.camera_id = "top"
        self.tracking_active = False
        self.fps = 0
        self.last_fps_time = time.time()
        self.frame_count = 0

        root = BoxLayout(orientation='vertical', padding=10, spacing=5)
        # Сервер
        root.add_widget(Label(text="Сервер:"))
        self.url_input = TextInput(text=self.server_url, multiline=False, size_hint=(1, 0.1))
        root.add_widget(self.url_input)
        # Камера
        root.add_widget(Label(text="ID камеры:"))
        self.cam_input = TextInput(text=self.camera_id, multiline=False, size_hint=(1, 0.1))
        root.add_widget(self.cam_input)
        # Статус
        self.info_label = Label(text="FPS: --", size_hint=(1, 0.1))
        root.add_widget(self.info_label)
        # Видоискатель
        self.camera_view = Image(size_hint=(1, 0.6))
        root.add_widget(self.camera_view)
        # Кнопки
        btn_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.15))
        self.track_btn = ToggleButton(text='Старт', on_press=self.toggle_tracking)
        self.quit_btn = Button(text='Выход', on_press=self.stop_app)
        btn_box.add_widget(self.track_btn)
        btn_box.add_widget(self.quit_btn)
        root.add_widget(btn_box)

        self.sender = NetworkSender(self.server_url)
        self.init_camera()
        Clock.schedule_interval(self.update_frame, 1/30.0)
        return root

    def init_camera(self):
        from kivy.core.camera import Camera as KivyCamera
        self.camera = KivyCamera(resolution=(1920,1080), play=True)

    def toggle_tracking(self, instance):
        self.tracking_active = instance.state == 'down'
        self.track_btn.text = 'Стоп' if self.tracking_active else 'Старт'

    def update_frame(self, dt):
        if not self.camera or not self.camera.texture: return
        texture = self.camera.texture
        frame = np.frombuffer(texture.pixels, dtype=np.uint8).reshape(texture.height, texture.width, 4)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        # Preview
        buf = cv2.flip(frame, 0).tobytes()
        tex = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
        tex.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.camera_view.texture = tex
        # Отправка кадра на сервер
        if self.tracking_active:
            ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                threading.Thread(target=self.sender.send_frame, args=(jpg.tobytes(), self.cam_input.text)).start()
        # FPS
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = now
            self.info_label.text = f"FPS: {self.fps}"

    def stop_app(self, instance):
        App.get_running_app().stop()

if __name__ == '__main__':
    JawTrackerApp().run()

if __name__ == '__main__':
    JawTrackerApp().run()
