#!/usr/bin/env python3
"""
JawTracker Mobile v3.0 — Максимальный функционал для Android
Локальный ArUco‑трекинг, настройки камеры, запись, визуализация, авто‑переподключение.
Совместим с сервером JawTracker v9.0.
"""

import cv2
import numpy as np
import socketio
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.utils import platform
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
import threading
import queue
import time
import json
import os
from datetime import datetime

# ================= НАСТРОЙКИ ПРИЛОЖЕНИЯ =================
class AppConfig:
    """Глобальные настройки с сохранением в JSON."""
    CONFIG_FILE = "camera_config.json"

    def __init__(self):
        # Сеть
        self.server_url = "http://192.168.1.100:5000"
        self.camera_id = "top"                # "top" или "front"
        self.send_to_server = True            # Отправлять данные на сервер или только локально

        # Камера
        self.camera_index = 0                 # 0 – задняя, 1 – передняя (не всегда переключается)
        self.resolution = (1920, 1080)        # Full HD
        self.fps_limit = 30
        self.show_preview = True
        self.show_axes = True                 # Рисовать оси маркеров на превью

        # Маркеры
        self.marker_ids = [0, 1, 2, 3]
        self.marker_sizes = {0: 120.0, 1: 30.0, 2: 120.0, 3: 30.0}   # мм

        # Калибровка
        self.camera_matrix = [[1800, 0, 960],
                              [0, 1800, 540],
                              [0, 0, 1]]
        self.dist_coeffs = [0, 0, 0, 0, 0]
        self.use_server_calibration = True    # Загружать калибровку с сервера при подключении

        # Запись
        self.record_video = False
        self.video_codec = 'mp4v'
        self.video_fps = 20

        # Прочее
        self.auto_reconnect = True
        self.voice_feedback = False           # Голосовые подсказки (требует pyttsx3, на Android сложно)

        self.load()

    def load(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
            except Exception as e:
                print(f"Ошибка загрузки конфига: {e}")

    def save(self):
        data = {
            'server_url': self.server_url,
            'camera_id': self.camera_id,
            'send_to_server': self.send_to_server,
            'camera_index': self.camera_index,
            'resolution': list(self.resolution),
            'fps_limit': self.fps_limit,
            'show_preview': self.show_preview,
            'show_axes': self.show_axes,
            'marker_ids': self.marker_ids,
            'marker_sizes': self.marker_sizes,
            'use_server_calibration': self.use_server_calibration,
            'record_video': self.record_video,
            'video_fps': self.video_fps,
            'auto_reconnect': self.auto_reconnect
        }
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")

# ================= ДЕТЕКТОР ArUco =================
class ArUcoDetector:
    def __init__(self, config):
        self.config = config
        self.dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters()
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 23
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(self.dictionary, params)

        self.K = np.array(self.config.camera_matrix, dtype=np.float32)
        self.dist = np.array(self.config.dist_coeffs, dtype=np.float32)

        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        self.marker_colors = {0: (0, 255, 0), 1: (255, 0, 0), 2: (0, 0, 255), 3: (255, 255, 0)}

    def process(self, frame):
        if frame is None:
            return None, frame

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(frame)

        results = {}
        if ids is not None:
            for i, mid in enumerate(ids.flatten()):
                if mid in self.config.marker_sizes:
                    rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                        corners[i].reshape(1,4,2),
                        self.config.marker_sizes[mid],
                        self.K, self.dist
                    )
                    # Ошибка репроекции
                    objp = np.array([[-self.config.marker_sizes[mid]/2, self.config.marker_sizes[mid]/2, 0],
                                     [ self.config.marker_sizes[mid]/2, self.config.marker_sizes[mid]/2, 0],
                                     [ self.config.marker_sizes[mid]/2,-self.config.marker_sizes[mid]/2, 0],
                                     [-self.config.marker_sizes[mid]/2,-self.config.marker_sizes[mid]/2, 0]], dtype=np.float32)
                    imgpts, _ = cv2.projectPoints(objp, rvec, tvec, self.K, self.dist)
                    error = np.mean(np.linalg.norm(corners[i][0] - imgpts.reshape(-1,2), axis=1))

                    results[int(mid)] = {
                        'rvec': rvec[0].tolist(),
                        'tvec': tvec[0].tolist(),
                        'quality': float(error)
                    }

                    # Отрисовка осей, если включено
                    if self.config.show_axes and frame is not None:
                        axis = np.float32([[30,0,0], [0,30,0], [0,0,30]]).reshape(-1,3)
                        imgpts2, _ = cv2.projectPoints(axis, rvec, tvec, self.K, self.dist)
                        corner = tuple(corners[i][0][0].astype(int))
                        imgpts2 = imgpts2.astype(int)
                        color = self.marker_colors.get(int(mid), (0,255,0))
                        cv2.line(frame, corner, tuple(imgpts2[0].ravel()), color, 3)
                        cv2.line(frame, corner, tuple(imgpts2[1].ravel()), (0,255,0), 3)
                        cv2.line(frame, corner, tuple(imgpts2[2].ravel()), (255,0,0), 3)

        # FPS
        self.fps_counter += 1
        if time.time() - self.last_fps_time >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_time = time.time()

        return results, frame

# ================= СЕТЕВОЙ КЛИЕНТ =================
class NetworkClient:
    def __init__(self, config):
        self.config = config
        self.sio = socketio.Client(
            reconnection=config.auto_reconnect,
            reconnection_attempts=0,  # бесконечно
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=False,
            engineio_logger=False
        )
        self.connected = False
        self.setup_handlers()

    def setup_handlers(self):
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            self.sio.emit('register_camera', {
                'camera_id': self.config.camera_id,
                'capabilities': ['aruco_detection'],
                'version': '3.0'
            })

        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False

        @self.sio.on('calibration_data')
        def on_calib(data):
            if hasattr(self, 'detector'):
                self.detector.K = np.array(data['camera_matrix'], dtype=np.float32)
                self.detector.dist = np.array(data['dist_coeffs'], dtype=np.float32)
                # Сохраним в конфиг
                self.config.camera_matrix = data['camera_matrix']
                self.config.dist_coeffs = data['dist_coeffs']
                self.config.save()

    def connect(self):
        try:
            self.sio.connect(self.config.server_url, transports=['websocket'])
        except Exception as e:
            print(f"Connection failed: {e}")

    def disconnect(self):
        if self.connected:
            self.sio.disconnect()

    def send_markers(self, markers):
        if self.connected and self.config.send_to_server:
            self.sio.emit('marker_data', {
                'camera_id': self.config.camera_id,
                'markers': markers,
                'timestamp': time.time()
            })

# ================= ГЛАВНОЕ ПРИЛОЖЕНИЕ =================
class JawTrackerApp(App):
    def build(self):
        self.config = AppConfig()
        self.detector = ArUcoDetector(self.config)
        self.network = NetworkClient(self.config)
        self.network.detector = self.detector
        self.tracking_active = False
        self.video_writer = None

        # Корневой layout
        root = BoxLayout(orientation='vertical', padding=8, spacing=5)

        # --- Верхняя панель: настройки (с прокруткой) ---
        scroll = ScrollView(size_hint=(1, 0.4))
        settings = GridLayout(cols=2, spacing=5, padding=5, size_hint_y=None)
        settings.bind(minimum_height=settings.setter('height'))

        # Сервер
        settings.add_widget(Label(text="Сервер:", size_hint_x=0.4))
        self.url_input = TextInput(text=self.config.server_url, multiline=False)
        settings.add_widget(self.url_input)

        # ID камеры
        settings.add_widget(Label(text="ID камеры:", size_hint_x=0.4))
        self.cam_spinner = Spinner(text=self.config.camera_id, values=['top', 'front'])
        settings.add_widget(self.cam_spinner)

        # Разрешение
        settings.add_widget(Label(text="Разрешение:", size_hint_x=0.4))
        self.res_spinner = Spinner(
            text=f"{self.config.resolution[0]}x{self.config.resolution[1]}",
            values=['1280x720', '1920x1080', '640x480']
        )
        settings.add_widget(self.res_spinner)

        # Отправка на сервер
        settings.add_widget(Label(text="Отправлять на сервер:", size_hint_x=0.4))
        self.send_check = CheckBox(active=self.config.send_to_server)
        self.send_check.bind(active=self.on_send_check)
        settings.add_widget(self.send_check)

        # Показывать оси
        settings.add_widget(Label(text="Показывать оси:", size_hint_x=0.4))
        self.axes_check = CheckBox(active=self.config.show_axes)
        self.axes_check.bind(active=self.on_axes_check)
        settings.add_widget(self.axes_check)

        # Запись видео
        settings.add_widget(Label(text="Запись видео:", size_hint_x=0.4))
        self.record_check = CheckBox(active=self.config.record_video)
        self.record_check.bind(active=self.on_record_check)
        settings.add_widget(self.record_check)

        scroll.add_widget(settings)
        root.add_widget(scroll)

        # --- Средняя панель: видоискатель ---
        self.camera_view = Image(size_hint=(1, 0.5))
        root.add_widget(self.camera_view)

        # --- Нижняя панель: статус и кнопки ---
        info_box = BoxLayout(orientation='vertical', size_hint=(1, 0.1))
        self.status_label = Label(text="● Отключено", color=(1,0.3,0.3,1), size_hint=(1, 0.5))
        self.info_label = Label(text="FPS: -- | Маркеры: -- | Качество: --", size_hint=(1, 0.5))
        info_box.add_widget(self.status_label)
        info_box.add_widget(self.info_label)
        root.add_widget(info_box)

        button_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.15))
        self.connect_btn = ToggleButton(text='Подключиться', on_press=self.toggle_connection)
        self.track_btn = ToggleButton(text='Старт', on_press=self.toggle_tracking, disabled=True)
        self.quit_btn = Button(text='Выход', on_press=self.stop_app)
        button_box.add_widget(self.connect_btn)
        button_box.add_widget(self.track_btn)
        button_box.add_widget(self.quit_btn)
        root.add_widget(button_box)

        # Инициализация камеры
        self.init_camera()

        # Запуск циклов
        Clock.schedule_interval(self.update_frame, 1.0 / self.config.fps_limit)
        Clock.schedule_interval(self.update_ui, 1.0)

        self.bind(on_stop=self.on_close)
        return root

    def init_camera(self):
        try:
            from kivy.core.camera import Camera as KivyCamera
            self.camera = KivyCamera(resolution=self.config.resolution, play=True)
        except Exception as e:
            self.status_label.text = f"Ошибка камеры: {e}"
            self.camera = None

    def on_send_check(self, instance, value):
        self.config.send_to_server = value

    def on_axes_check(self, instance, value):
        self.config.show_axes = value

    def on_record_check(self, instance, value):
        self.config.record_video = value
        if value and self.tracking_active:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if self.video_writer is None and self.camera:
            fourcc = cv2.VideoWriter_fourcc(*self.config.video_codec)
            fname = f"jawtrack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            self.video_writer = cv2.VideoWriter(fname, fourcc, self.config.video_fps, self.config.resolution)
            print(f"Запись начата: {fname}")

    def stop_recording(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
            print("Запись остановлена")

    def update_frame(self, dt):
        if not self.camera or not self.camera.texture:
            return
        texture = self.camera.texture
        frame = np.frombuffer(texture.pixels, dtype=np.uint8).reshape(texture.height, texture.width, 4)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # Детекция и отрисовка осей (если включены)
        markers, annotated_frame = self.detector.process(frame)

        # Запись видео
        if self.config.record_video and self.video_writer:
            self.video_writer.write(annotated_frame)

        # Preview
        if self.config.show_preview:
            buf = cv2.flip(annotated_frame, 0).tobytes()
            tex = Texture.create(size=(annotated_frame.shape[1], annotated_frame.shape[0]), colorfmt='bgr')
            tex.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.camera_view.texture = tex

        # Отправка на сервер
        if markers and self.tracking_active:
            self.network.send_markers(markers)
            avg_q = np.mean([m['quality'] for m in markers.values()])
            self.info_label.text = f"FPS: {self.detector.current_fps:.0f} | Маркеры: {len(markers)} | Качество: {avg_q:.2f}px"

    def update_ui(self, dt):
        if self.network.connected:
            self.status_label.text = "● Подключено"
            self.status_label.color = (0.2,1,0.2,1)
        else:
            self.status_label.text = "● Отключено"
            self.status_label.color = (1,0.3,0.3,1)

    def toggle_connection(self, instance):
        if instance.state == 'down':
            self.config.server_url = self.url_input.text
            self.config.camera_id = self.cam_spinner.text
            # Разрешение
            w, h = map(int, self.res_spinner.text.split('x'))
            self.config.resolution = (w, h)
            self.config.save()

            self.network.connect()
            self.connect_btn.text = 'Отключиться'
            self.track_btn.disabled = False
        else:
            self.network.disconnect()
            self.connect_btn.text = 'Подключиться'
            self.track_btn.disabled = True

    def toggle_tracking(self, instance):
        self.tracking_active = instance.state == 'down'
        self.track_btn.text = 'Стоп' if self.tracking_active else 'Старт'

        if self.tracking_active and self.config.record_video:
            self.start_recording()
        elif not self.tracking_active:
            self.stop_recording()

    def stop_app(self, instance):
        self.stop_recording()
        self.network.disconnect()
        self.config.save()
        App.get_running_app().stop()

    def on_close(self, instance):
        self.stop_recording()
        self.network.disconnect()
        self.config.save()

if __name__ == '__main__':
    JawTrackerApp().run()