#!/usr/bin/env python3
"""
JawTracker Camera Sender – отправляет сжатые JPEG на сервер.
Использует рецепт opencv (python-for-android), requests.
"""
import cv2
import numpy as np
import requests
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

class FrameSender:
    """Отправляет JPEG кадры на сервер через HTTP POST."""
    def __init__(self, server_url):
        self.server_url = server_url
        self.session = requests.Session()

    def send(self, jpg_bytes, camera_id):
        try:
            files = {'frame': ('frame.jpg', jpg_bytes, 'image/jpeg')}
            data = {'camera_id': camera_id}
            self.session.post(
                f"{self.server_url}/upload_frame",
                files=files, data=data, timeout=0.5
            )
        except Exception:
            pass

class CameraSenderApp(App):
    def build(self):
        self.server_url = "http://192.168.1.100:5000"
        self.camera_id = "top"
        self.is_sending = False
        self.fps = 0
        self.frame_cnt = 0
        self.last_fps = time.time()

        # --- Интерфейс ---
        root = BoxLayout(orientation='vertical', padding=10, spacing=5)

        root.add_widget(Label(text="IP сервера:", size_hint=(1, 0.08)))
        self.url_entry = TextInput(text=self.server_url, multiline=False, size_hint=(1, 0.08))
        root.add_widget(self.url_entry)

        root.add_widget(Label(text="ID камеры:", size_hint=(1, 0.08)))
        self.cam_entry = TextInput(text=self.camera_id, multiline=False, size_hint=(1, 0.08))
        root.add_widget(self.cam_entry)

        self.info_label = Label(text="FPS: --", size_hint=(1, 0.08))
        root.add_widget(self.info_label)

        self.camera_view = Image(size_hint=(1, 0.55))
        root.add_widget(self.camera_view)

        btn_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.12))
        self.start_btn = ToggleButton(text='▶ Отправка', on_press=self.toggle_sending)
        quit_btn = Button(text='Выход', on_press=self.stop_app)
        btn_box.add_widget(self.start_btn)
        btn_box.add_widget(quit_btn)
        root.add_widget(btn_box)

        # --- Камера ---
        from kivy.core.camera import Camera as KivyCamera
        self.camera = KivyCamera(resolution=(1920, 1080), play=True)
        self.sender = FrameSender(self.server_url)

        Clock.schedule_interval(self.process_frame, 1 / 30.0)
        return root

    def toggle_sending(self, instance):
        self.is_sending = instance.state == 'down'
        instance.text = '⏸ Стоп' if self.is_sending else '▶ Отправка'

    def process_frame(self, dt):
        if not self.camera or not self.camera.texture:
            return
        texture = self.camera.texture
        # Конвертация Kivy-текстуры в numpy-массив
        frame = np.frombuffer(texture.pixels, dtype=np.uint8)
        frame = frame.reshape(texture.height, texture.width, 4)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # Preview (показываем, что снимает камера)
        buf = cv2.flip(frame, 0).tobytes()
        tex = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
        tex.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.camera_view.texture = tex

        # Отправка кадра
        if self.is_sending:
            ok, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ok:
                threading.Thread(
                    target=self.sender.send,
                    args=(jpg.tobytes(), self.cam_entry.text),
                    daemon=True
                ).start()

        # Счётчик FPS
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
    CameraSenderApp().run()
