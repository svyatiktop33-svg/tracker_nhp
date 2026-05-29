#!/usr/bin/env python3
"""
JawTracker Camera – отправляет JPEG кадры на сервер.
Не требует OpenCV, только Kivy + requests.
"""
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.core.camera import Camera as KivyCamera
import time
import threading
from io import BytesIO
from PIL import Image as PILImage

class FrameSender:
    def __init__(self, server_url):
        self.server_url = server_url

    def send(self, jpg_bytes, camera_id):
        try:
            files = {'frame': ('frame.jpg', jpg_bytes, 'image/jpeg')}
            data = {'camera_id': camera_id}
            requests.post(f"{self.server_url}/upload_frame",
                          files=files, data=data, timeout=0.5)
        except:
            pass

class CameraApp(App):
    def build(self):
        self.server_url = "http://192.168.1.100:5000"
        self.camera_id = "top"
        self.sending = False
        self.fps = 0
        self.frame_cnt = 0
        self.last_fps = time.time()

        root = BoxLayout(orientation='vertical', padding=10, spacing=5)

        root.add_widget(Label(text="IP сервера:"))
        self.url_entry = TextInput(text=self.server_url, multiline=False)
        root.add_widget(self.url_entry)

        root.add_widget(Label(text="ID камеры:"))
        self.cam_entry = TextInput(text=self.camera_id, multiline=False)
        root.add_widget(self.cam_entry)

        self.info_label = Label(text="FPS: --")
        root.add_widget(self.info_label)

        self.camera_view = Image()
        root.add_widget(self.camera_view)

        btn_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.1))
        self.start_btn = ToggleButton(text='▶ Отправка', on_press=self.toggle_sending)
        btn_box.add_widget(self.start_btn)
        btn_box.add_widget(Button(text='Выход', on_press=self.stop_app))
        root.add_widget(btn_box)

        self.camera = KivyCamera(resolution=(1920, 1080), play=True)
        self.sender = FrameSender(self.server_url)

        Clock.schedule_interval(self.process_frame, 1 / 30.0)
        return root

    def toggle_sending(self, instance):
        self.sending = instance.state == 'down'
        instance.text = '⏸ Стоп' if self.sending else '▶ Отправка'

    def process_frame(self, dt):
        if not self.camera or not self.camera.texture:
            return
        texture = self.camera.texture
        size = texture.size
        pixels = texture.pixels
        # Преобразуем в JPEG с помощью Pillow (уже есть в kivy)
        img = PILImage.frombytes('RGBA', size, pixels.tobytes())
        img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=60)
        jpg_bytes = buf.getvalue()

        self.camera_view.texture = texture

        if self.sending:
            threading.Thread(target=self.sender.send,
                             args=(jpg_bytes, self.cam_entry.text)).start()

        self.frame_cnt += 1
        now = time.time()
        if now - self.last_fps >= 1.0:
            self.fps = self.frame_cnt
            self.frame_cnt = 0
            self.last_fps = now
            self.info_label.text = f"FPS: {self.fps}"

    def stop_app(self, instance):
        App.get_running_app().stop()

if __name__ == '__main__':
    CameraApp().run()
