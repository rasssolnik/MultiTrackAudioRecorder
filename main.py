import os
import sounddevice as sd
import soundfile as sf
import numpy as np
from tkinter import *
from tkinter import ttk, filedialog, messagebox
import threading
import time
from datetime import datetime
import keyboard
from collections import deque

class AudioRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Многодорожечный аудиорекордер")
        self.root.geometry("800x750")
        
        # Переменные
        self.selected_inputs = set()
        self.is_recording = False
        self.is_buffering = False
        self.recording_thread = None
        self.timer_thread = None
        self.buffer_thread = None
        self.countdown_seconds = 0
        self.output_dir = r"C:\MultiTrackRecorder"
        self.streams = []
        self.audio_data = {}
        self.buffer_data = {}
        self.use_timer = BooleanVar(value=False)
        self.show_all_devices = False
        self.instant_replay = BooleanVar(value=False)
        self.buffer_duration = IntVar(value=2)
        self.hotkey = "shift+f10"
        self.record_hotkey = "ctrl+shift+r"
        self.buffer_queue = {}
        self.buffer_streams = []
        self.hotkey_listener = None
        self.record_hotkey_listener = None
        self.last_buffer_duration = 2
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.create_widgets()
        self.update_device_list()
        self.setup_hotkeys()

    def toggle_recording(self):
        """Переключает состояние записи"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def on_buffer_duration_change(self, event=None):
        """Обработчик изменения длительности буфера"""
        if self.is_buffering:
            self.buffer_slider.set(self.last_buffer_duration)
            messagebox.showwarning("Предупреждение", 
                                "Нельзя изменять длительность буфера во время работы. "
                                "Сначала остановите буферизацию.")
        else:
            self.last_buffer_duration = self.buffer_duration.get()
    
    def remove_hotkeys(self):
        """Безопасное удаление горячих клавиш"""
        try:
            if self.hotkey_listener:
                keyboard.remove_hotkey(self.hotkey_listener)
                self.hotkey_listener = None
        except Exception as e:
            print(f"Ошибка удаления hotkey: {e}")
        
        try:
            if self.record_hotkey_listener:
                keyboard.remove_hotkey(self.record_hotkey_listener)
                self.record_hotkey_listener = None
        except Exception as e:
            print(f"Ошибка удаления record_hotkey: {e}")

    def setup_hotkeys(self):
        """Настройка горячих клавиш с обработкой ошибок"""
        try:
            self.remove_hotkeys()
            
            # Горячая клавиша для записи
            self.record_hotkey_listener = keyboard.add_hotkey(
                self.record_hotkey,
                self.toggle_recording,
                suppress=True
            )
            
            # Горячая клавиша для повтора только если включен режим
            if self.instant_replay.get():
                self.hotkey_listener = keyboard.add_hotkey(
                    self.hotkey,
                    self.save_buffer_manually,
                    suppress=True
                )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Проблема с горячими клавишами: {str(e)}")
            self.instant_replay.set(False)
            self.remove_hotkeys()

    def safe_toggle_recording(self):
        """Безопасный вызов toggle_recording из другого потока"""
        self.root.after(0, self.toggle_recording)

    def safe_save_buffer_manually(self):
        """Безопасный вызов save_buffer_manually из другого потока"""
        self.root.after(0, self.save_buffer_manually)

    def set_hotkey(self):
        if self.is_recording:
            messagebox.showwarning("Предупреждение", "Нельзя изменять настройки во время записи")
            return
            
        dialog = Toplevel(self.root)
        dialog.title("Установка горячей клавиши")
        dialog.geometry("400x200")
        
        Label(dialog, text="Нажмите комбинацию клавиш (ТОЛЬКО АНГЛИЙСКИЕ БУКВЫ)").pack(pady=5)
        Label(dialog, text="(Например: Shift+F10)").pack()
        Label(dialog, text="Затем нажмите Enter для подтверждения").pack()
        
        key_combination = []
        label = Label(dialog, text="", font=('Arial', 12))
        label.pack(pady=10)
        error_label = Label(dialog, text="", fg="red")
        error_label.pack()
        
        def on_key(event):
            if event.keysym.lower() in ['win_l', 'win_r', 'windows', 'meta_l', 'meta_r', '??']:
                error_label.config(text="Кнопка запрещена!")
                return
            
            if event.keysym == "Return":
                if key_combination:
                    new_hotkey = "+".join(key_combination)
                    
                    if new_hotkey.lower() == self.record_hotkey.lower():
                        error_label.config(text="Эта комбинация уже используется для записи!")
                        return
                    
                    self.hotkey = new_hotkey
                    self.hotkey_btn.config(text=self.hotkey)
                    self.remove_hotkeys()
                    self.setup_hotkeys()
                    dialog.destroy()
                return
            
            key_name = event.keysym.lower()
            if key_name in ['shift_l', 'shift_r']:
                key_name = 'shift'
            elif key_name in ['alt_l', 'alt_r']:
                key_name = 'alt'
            elif key_name in ['control_l', 'control_r']:
                key_name = 'ctrl'
            
            if key_name not in key_combination:
                key_combination.append(key_name)
                display_keys = [k.upper() for k in key_combination]
                label.config(text=f"Выбрано: {'+'.join(display_keys)}")
                error_label.config(text="")
        
        dialog.bind("<Key>", on_key)
        dialog.grab_set()
        dialog.focus_set()

    def set_record_hotkey(self):
        if self.is_recording:
            messagebox.showwarning("Предупреждение", "Нельзя изменять настройки во время записи")
            return
            
        dialog = Toplevel(self.root)
        dialog.title("Установка горячей клавиши")
        dialog.geometry("400x200")
        
        Label(dialog, text="Нажмите комбинацию клавиш (ТОЛЬКО АНГЛИЙСКИМИ БУКВАМИ)").pack(pady=5)
        Label(dialog, text="(Например: Ctrl+Shift+R)").pack()
        Label(dialog, text="Затем нажмите Enter для подтверждения").pack()
        
        key_combination = []
        label = Label(dialog, text="", font=('Arial', 12))
        label.pack(pady=10)
        error_label = Label(dialog, text="", fg="red")
        error_label.pack()
        
        def on_key(event):
            if event.keysym.lower() in ['win_l', 'win_r', 'windows', 'meta_l', 'meta_r', '??']:
                error_label.config(text="Кнопка запрещена!")
                return
                
            if event.keysym == "Return":
                if key_combination:
                    new_hotkey = "+".join(key_combination)
                    
                    if new_hotkey.lower() == self.hotkey.lower():
                        error_label.config(text="Эта комбинация уже используется для повтора!")
                        return
                    
                    self.record_hotkey = new_hotkey
                    self.record_hotkey_btn.config(text=self.record_hotkey)
                    self.remove_hotkeys()
                    self.setup_hotkeys()
                    dialog.destroy()
                return
                
            key_name = event.keysym.lower()
            if key_name in ['shift_l', 'shift_r']:
                key_name = 'shift'
            elif key_name in ['alt_l', 'alt_r']:
                key_name = 'alt'
            elif key_name in ['control_l', 'control_r']:
                key_name = 'ctrl'
            
            if key_name not in key_combination:
                key_combination.append(key_name)
                display_keys = [k.upper() for k in key_combination]
                label.config(text=f"Выбрано: {'+'.join(display_keys)}")
                error_label.config(text="")
        
        dialog.bind("<Key>", on_key)
        dialog.grab_set()
        dialog.focus_set()

    def validate_input_devices(self):
        """Проверяет доступность выбранных устройств"""
        if not self.device_tree.selection():
            messagebox.showwarning("Предупреждение", "Сначала выберите устройства для записи")
            return False
            
        self.selected_inputs = set()
        for item in self.device_tree.selection():
            values = self.device_tree.item(item, 'values')
            device_idx = int(values[0])
            if "Input" in values[2]:
                self.selected_inputs.add(device_idx)
        
        if not self.selected_inputs:
            messagebox.showwarning("Предупреждение", "Не выбрано ни одного входного устройства")
            return False
        
        return True

    def toggle_instant_replay(self):
        """Переключает мгновенный повтор с защитой от ошибок"""
        try:
            if self.instant_replay.get():
                if not self.validate_input_devices():
                    self.instant_replay.set(False)
                    return
                    
                self.start_buffering()
            else:
                self.stop_buffering()
                
            self.setup_hotkeys()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при переключении режима: {str(e)}")
            self.instant_replay.set(False)
            self.setup_hotkeys()

    def start_buffering(self):
        """Запускает буферизацию с проверкой состояния"""
        if self.is_buffering:
            return
            
        if not self.selected_inputs:
            raise ValueError("Не выбраны устройства для буферизации")
        
        self.is_buffering = True
        self.buffer_data = {}
        self.buffer_queue = {}
        self.buffer_status.config(text=f"Буфер: активен ({self.buffer_duration.get()} мин)", fg="green")
        self.save_buffer_btn.config(state="normal")
        
        # Останавливаем предыдущий поток, если он есть
        if self.buffer_thread and self.buffer_thread.is_alive():
            self.stop_buffering()
            time.sleep(0.2)
        
        self.buffer_thread = threading.Thread(target=self.buffer_audio, daemon=True)
        self.buffer_thread.start()

    def stop_buffering(self):
        """Останавливает буферизацию с полной очисткой"""
        if not self.is_buffering:
            return
        
        self.is_buffering = False
        self.buffer_status.config(text="Буфер: выключен", fg="gray")
        self.save_buffer_btn.config(state="disabled")
        
        # Даем время потоку завершиться
        time.sleep(0.1)
        
        # Очищаем данные буфера
        self.buffer_queue = {}
        self.buffer_data = {}

    def buffer_audio(self):
        """Функция буферизации аудио"""
        sample_rate = 44100
        buffer_duration_seconds = self.buffer_duration.get() * 60
        max_samples = int(sample_rate * buffer_duration_seconds)
        
        self.buffer_queue = {idx: deque(maxlen=max_samples) for idx in self.selected_inputs}
        
        def callback(indata, frames, time, status, device_idx):
            if self.is_buffering and device_idx in self.buffer_queue:
                self.buffer_queue[device_idx].extend(indata.copy())
        
        self.buffer_streams = []
        try:
            for device_idx in self.selected_inputs:
                device_info = sd.query_devices(device_idx)
                channels = min(2, device_info['max_input_channels'])
                
                stream = sd.InputStream(
                    device=device_idx,
                    channels=channels,
                    samplerate=sample_rate,
                    callback=lambda indata, frames, time, status, idx=device_idx: callback(indata, frames, time, status, idx),
                    dtype='float32'
                )
                self.buffer_streams.append(stream)
                stream.start()
            
            while self.is_buffering:
                time.sleep(0.1)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка буферизации", str(e)))
        finally:
            for stream in self.buffer_streams:
                try:
                    stream.stop()
                    stream.close()
                except:
                    pass
            self.buffer_streams = []

    def save_buffer_manually(self):
        if not self.is_buffering or not self.buffer_queue:
            messagebox.showwarning("Предупреждение", "Буферизация не активна или данные отсутствуют")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []
        
        for device_idx, data_queue in self.buffer_queue.items():
            if not data_queue:
                continue
                
            try:
                device_name = sd.query_devices(device_idx)['name']
                safe_name = "".join(c if c.isalnum() else "_" for c in device_name)
                filename = f"buffer_{safe_name}_{timestamp}.wav"
                filepath = os.path.join(self.output_dir, filename)
                
                channels = min(2, sd.query_devices(device_idx)['max_input_channels'])
                audio_data = np.array(list(data_queue)).reshape(-1, channels)
                sf.write(filepath, audio_data, 44100, format='WAV')
                saved_files.append(filepath)  # Сохраняем полный путь
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", 
                                   f"Не удалось сохранить буфер с устройства {device_idx}:\n{str(e)}")
        
        if saved_files:
            messagebox.showinfo("Готово", 
                              f"Буфер успешно сохранен по пути:\n{self.output_dir}\n\n"
                              f"Сохраненные файлы:\n{'\n'.join(saved_files)}")

    def start_recording(self):
        """Начинает запись с проверкой устройств"""
        selected_items = self.device_tree.selection()
        if not selected_items:
            messagebox.showerror("Ошибка", "Выберите хотя бы одно устройство для записи")
            return
        
        self.selected_inputs = set()
        valid_devices = []
        invalid_devices = []
        
        for item in selected_items:
            values = self.device_tree.item(item, 'values')
            device_idx = int(values[0])
            device_name = values[1]
            
            try:
                # Проверяем, что устройство действительно доступно для записи
                device_info = sd.query_devices(device_idx)
                if device_info['max_input_channels'] > 0:
                    # Проверяем, что устройство можно открыть
                    test_stream = sd.InputStream(device=device_idx, channels=1, samplerate=44100)
                    test_stream.close()
                    self.selected_inputs.add(device_idx)
                    valid_devices.append(device_name)
                else:
                    invalid_devices.append(device_name)
            except Exception as e:
                invalid_devices.append(f"{device_name} (ошибка: {str(e)})")
                continue
        
        if not self.selected_inputs:
            messagebox.showerror("Ошибка", 
                f"Не выбрано ни одного рабочего входного устройства.\nПроблемные устройства:\n{', '.join(invalid_devices)}")
            return
        
        if invalid_devices:
            messagebox.showwarning("Предупреждение", 
                f"Следующие устройства не будут записаны:\n{', '.join(invalid_devices)}")
        
        # Остальная часть метода остается без изменений
        try:
            if self.use_timer.get():
                self.countdown_seconds = int(self.timer_entry.get())
                if self.countdown_seconds <= 0:
                    raise ValueError
            else:
                self.countdown_seconds = 0
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное значение таймера (положительное число)")
            return
        
        self.audio_data = {idx: [] for idx in self.selected_inputs}
        self.is_recording = True
        self.record_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Запись...")
        
        if self.instant_replay.get():
            self.start_buffering()
        
        if self.countdown_seconds > 0:
            self.timer_label.config(text=f"Таймер: {self.countdown_seconds} сек")
            self.timer_thread = threading.Thread(target=self.countdown_timer, daemon=True)
            self.timer_thread.start()
        
        self.recording_thread = threading.Thread(target=self.record_audio, daemon=True)
        self.recording_thread.start()

    def treeview_sort_column(self, col, reverse):
        """Сортировка Treeview по колонке"""
        l = [(self.device_tree.set(k, col), k) for k in self.device_tree.get_children('')]
        try:
            # Пробуем преобразовать к числу (для ID)
            l.sort(key=lambda t: int(t[0]), reverse=reverse)
        except ValueError:
            # Если не число, сортируем как строки
            l.sort(reverse=reverse)
        
        # Перемещаем элементы в отсортированном порядке
        for index, (val, k) in enumerate(l):
            self.device_tree.move(k, '', index)
        
        # Устанавливаем обратную сортировку для следующего клика
        self.device_tree.heading(col, command=lambda _col=col: self.treeview_sort_column(_col, not reverse))

    def stop_recording(self):
        """Останавливает запись"""
        self.is_recording = False
        self.stop_buffering()
        self.status_label.config(text="Запись остановлена")
        self.record_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def record_audio(self):
        """Функция записи аудио"""
        sample_rate = 44100
        self.streams = []
        
        try:
            for device_idx in self.selected_inputs:
                device_info = sd.query_devices(device_idx)
                channels = min(2, device_info['max_input_channels'])
                
                def make_callback(idx):
                    return lambda indata, frames, time, status: self.audio_callback(indata, idx)
                
                stream = sd.InputStream(
                    device=device_idx,
                    channels=channels,
                    samplerate=sample_rate,
                    callback=make_callback(device_idx),
                    dtype='float32'
                )
                self.streams.append(stream)
                stream.start()
            
            while self.is_recording:
                time.sleep(0.1)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка записи", str(e)))
        finally:
            for stream in self.streams:
                try:
                    stream.stop()
                    stream.close()
                except:
                    pass
            
            self.root.after(0, self.save_audio_files, sample_rate)

    def audio_callback(self, indata, device_idx):
        """Callback для записи аудиоданных"""
        if self.is_recording:
            self.audio_data[device_idx].append(indata.copy())

    def save_audio_files(self, sample_rate):
        """Сохраняет записанные аудиофайлы"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []
        
        for device_idx, data_list in self.audio_data.items():
            if not data_list:
                continue
                
            try:
                device_name = sd.query_devices(device_idx)['name']
                safe_name = "".join(c if c.isalnum() else "_" for c in device_name)
                filename = f"recording_{safe_name}_{timestamp}.wav"
                filepath = os.path.join(self.output_dir, filename)
                
                audio_data = np.concatenate(data_list)
                sf.write(filepath, audio_data, sample_rate, format='WAV')
                saved_files.append(filepath)  # Сохраняем полный путь
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", 
                    f"Не удалось сохранить запись с устройства {device_idx}:\n{str(e)}")
        
        if saved_files:
            messagebox.showinfo("Готово", 
                f"Аудиофайлы успешно сохранены по пути:\n{self.output_dir}\n\n"
                f"Сохраненные файлы:\n{'\n'.join(saved_files)}")
        
        self.audio_data = {}
        self.root.after(0, lambda: self.status_label.config(text="Готов к записи"))

    def countdown_timer(self):
        while self.countdown_seconds > 0 and self.is_recording:
            time.sleep(1)
            self.countdown_seconds -= 1
            self.root.after(0, self.update_timer_display, self.countdown_seconds)
        
        if self.countdown_seconds <= 0 and self.is_recording:
            self.root.after(0, self.stop_recording)

    def update_timer_display(self, seconds):
        """Обновляет отображение таймера"""
        self.timer_label.config(text=f"Таймер: {seconds} сек")

    def toggle_timer_entry(self):
        if self.use_timer.get():
            self.timer_entry.config(state="normal")
        else:
            self.timer_entry.config(state="disabled")
            self.timer_label.config(text="")

    def toggle_devices_view(self):
        """Переключает отображение устройств"""
        self.show_all_devices = not self.show_all_devices
        self.toggle_devices_btn.config(text="Скрыть все устройства" if self.show_all_devices 
                                     else "Показать только Line In")
        self.update_device_list()

    def update_device_list(self):
        """Обновляет список устройств с возможностью сортировки"""
        self.device_tree.delete(*self.device_tree.get_children())
        devices = sd.query_devices()
        
        for i, dev in enumerate(devices):
            # Пропускаем чисто выходные устройства
            if dev['max_input_channels'] == 0:
                continue
                
            device_type = "Input" if dev['max_input_channels'] > 0 else "Output"
            name_lower = dev['name'].lower()
            
            # Если показываем не все устройства, применяем фильтр
            if not self.show_all_devices:
                # Проверяем, что это входное устройство и содержит 'line' 
                # но не содержит 'out' (чтобы исключить выходные)
                if not ('line' in name_lower and 'output' not in name_lower and 'virtual' in name_lower):
                    continue
            
            self.device_tree.insert('', 'end', values=(i, dev['name'], device_type))
        
        # Добавляем сортировку по колонкам
        for col in self.device_tree['columns']:
            self.device_tree.heading(col, command=lambda _col=col: self.treeview_sort_column(_col, False))

    def browse_directory(self):
        """Выбор директории для сохранения"""
        directory = filedialog.askdirectory(initialdir=self.output_dir)
        if directory:
            self.output_dir = directory
            self.dir_entry.delete(0, END)
            self.dir_entry.insert(0, directory)

    def create_widgets(self):
        main_frame = Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Фрейм для выбора устройств
        device_frame = LabelFrame(main_frame, text="Выбор аудиоустройств", padx=5, pady=5)
        device_frame.pack(fill="both", expand=True, pady=5)
        
        # Treeview с колонками
        self.device_tree = ttk.Treeview(device_frame, columns=('id', 'name', 'type'), show='headings', height=8, selectmode='extended')
        self.device_tree.heading('id', text='ID', anchor='center', command=lambda: self.treeview_sort_column('id', False))
        self.device_tree.heading('name', text='Название устройства', anchor='w', command=lambda: self.treeview_sort_column('name', False))
        self.device_tree.heading('type', text='Тип', anchor='center', command=lambda: self.treeview_sort_column('type', False))
        
        self.device_tree.column('id', width=50, anchor='center', stretch=False)
        self.device_tree.column('name', anchor='w', stretch=True)
        self.device_tree.column('type', width=80, anchor='center', stretch=False)
        
        scrollbar = ttk.Scrollbar(device_frame, orient="vertical", command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        
        self.device_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Настройки записи
        settings_frame = LabelFrame(main_frame, text="Настройки записи", padx=5, pady=5)
        settings_frame.pack(fill="x", pady=5)
        
        # Таймер
        timer_frame = Frame(settings_frame)
        timer_frame.pack(side="left", padx=5)
        Checkbutton(timer_frame, text="Использовать таймер", variable=self.use_timer, command=self.toggle_timer_entry).pack(side="left")
        Label(timer_frame, text="Длительность (секунды):").pack(side="left", padx=5)
        self.timer_entry = Entry(timer_frame, width=8)
        self.timer_entry.pack(side="left")
        self.timer_entry.insert(0, "60")
        self.timer_entry.config(state="disabled")
        
        # Директория для сохранения
        dir_frame = Frame(settings_frame)
        dir_frame.pack(fill="x", pady=2)
        Label(dir_frame, text="Директория для сохранения:").pack(side="left")
        self.dir_entry = Entry(dir_frame)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.dir_entry.insert(0, self.output_dir)
        Button(dir_frame, text="Обзор...", command=self.browse_directory).pack(side="left")
        
        # Настройки мгновенного повтора
        replay_frame = LabelFrame(main_frame, text="Мгновенный повтор", padx=5, pady=5)
        replay_frame.pack(fill="x", pady=5)
        
        Checkbutton(replay_frame, text="Включить мгновенный повтор", variable=self.instant_replay,
                  command=self.toggle_instant_replay).pack(anchor="w")
        
        # Ползунок для длительности буфера
        buffer_frame = Frame(replay_frame)
        buffer_frame.pack(fill="x", pady=2)
        Label(buffer_frame, text="Длительность буфера:").pack(side="left")
        self.buffer_slider = Scale(buffer_frame, from_=1, to=20, orient=HORIZONTAL, 
                                variable=self.buffer_duration, command=self.on_buffer_duration_change)
        self.buffer_slider.pack(side="left", fill="x", expand=True, padx=5)
        Label(buffer_frame, text="мин").pack(side="left")
        
        # Горячие клавиши (фиксированного размера)
        hotkey_frame = Frame(replay_frame)
        hotkey_frame.pack(fill="x", pady=2)
        
        Label(hotkey_frame, text="Горячая клавиша повтора:").pack(side="left")
        self.hotkey_btn = Button(hotkey_frame, text=self.hotkey, command=self.set_hotkey, width=15)
        self.hotkey_btn.pack(side="left", padx=5)
        
        Label(hotkey_frame, text="Горячая клавиша записи:").pack(side="left", padx=(10,0))
        self.record_hotkey_btn = Button(hotkey_frame, text=self.record_hotkey, command=self.set_record_hotkey, width=15)
        self.record_hotkey_btn.pack(side="left", padx=5)
        
        # Управление записью
        control_frame = Frame(main_frame)
        control_frame.pack(fill="x", pady=5)
        
        btn_height = 2
        btn_font = ('Arial', 10, 'bold')
        
        self.record_btn = Button(control_frame, text="Начать запись", command=self.start_recording, 
                               bg="#4CAF50", fg="white", height=btn_height, font=btn_font)
        self.record_btn.pack(side="left", expand=True, fill="x", padx=2)
        
        self.stop_btn = Button(control_frame, text="Остановить запись", command=self.stop_recording, 
                             state="disabled", height=btn_height, 
                             bg="#F44336", fg="white", font=btn_font)
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=2)
        
        self.save_buffer_btn = Button(control_frame, text="Сохранить буфер", command=self.save_buffer_manually,
                                    state="disabled", height=btn_height, font=btn_font)
        self.save_buffer_btn.pack(side="left", expand=True, fill="x", padx=2)
        
        self.toggle_devices_btn = Button(control_frame, text="Показать все устройства", 
                                      command=self.toggle_devices_view,
                                      height=btn_height, font=btn_font)
        self.toggle_devices_btn.pack(side="left", expand=True, fill="x", padx=2)
        
        # Статус
        self.status_label = Label(main_frame, text="Готов к записи", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", pady=5)
        self.timer_label = Label(main_frame, text="", fg="blue")
        self.timer_label.pack(fill="x")
        self.buffer_status = Label(main_frame, text="Буфер: выключен", fg="gray")
        self.buffer_status.pack(fill="x")

if __name__ == "__main__":
    root = Tk()
    app = AudioRecorderApp(root)
    
    try:
        root.mainloop()
    finally:
        keyboard.unhook_all()