import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QProgressBar,
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                             QFileDialog, QMenuBar, QMenu, QStatusBar, QMessageBox,
                             QComboBox, QDialog, QTextEdit, QGroupBox, QRadioButton,
                             QButtonGroup, QCheckBox, QSpinBox, QTabWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction

from downloader import (DownloadManager, EventType, Status, 
                       VideoFormat, VideoQuality, VideoInfo,
                       URLParser, VideoInfoExtractor)


class FormatDialog(QDialog):
    def __init__(self, video_info: VideoInfo, parent=None):
        super().__init__(parent)
        self.video_info = video_info
        self.selected_format = None
        self.selected_quality = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Выбор качества")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel(f"<b>{self.video_info.title}</b>")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        duration = self.video_info.duration
        if duration:
            mins, secs = divmod(duration, 60)
            info_label2 = QLabel(f"Длительность: {mins}:{secs:02d} | Загрузчик: {URLParser.get_platform_name(self.video_info.url)}")
            layout.addWidget(info_label2)
        
        layout.addWidget(QLabel("<b>Формат:</b>"))
        
        format_group = QButtonGroup(self)
        self.format_buttons = {}
        
        formats_layout = QHBoxLayout()
        for fmt in VideoFormat:
            rb = QRadioButton(fmt.value.upper())
            rb.setObjectName(fmt.value)
            format_group.addButton(rb)
            formats_layout.addWidget(rb)
            self.format_buttons[fmt] = rb
        
        self.format_buttons[VideoFormat.BEST].setChecked(True)
        layout.addLayout(formats_layout)
        
        layout.addWidget(QLabel("<b>Качество видео:</b>"))
        
        quality_combo = QComboBox()
        quality_combo.addItem("Лучшее", VideoQuality.BEST)
        quality_combo.addItem("4K (2160p)", VideoQuality.QUALITY_4K)
        quality_combo.addItem("1440p", VideoQuality.QUALITY_1440)
        quality_combo.addItem("1080p", VideoQuality.QUALITY_1080)
        quality_combo.addItem("720p", VideoQuality.QUALITY_720)
        quality_combo.addItem("480p", VideoQuality.QUALITY_480)
        quality_combo.addItem("360p", VideoQuality.QUALITY_360)
        quality_combo.addItem("240p", VideoQuality.QUALITY_240)
        self.quality_combo = quality_combo
        layout.addWidget(quality_combo)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("Скачать")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def get_selection(self):
        for fmt, btn in self.format_buttons.items():
            if btn.isChecked():
                self.selected_format = fmt
                break
        
        self.selected_quality = self.quality_combo.currentData()
        return self.selected_format, self.selected_quality


class ProgressEmitter(QThread):
    progress_signal = pyqtSignal(dict)
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.running = True
        
    def run(self):
        def on_progress(data):
            self.progress_signal.emit(data)
        
        def on_completed(data):
            self.progress_signal.emit(data)
        
        def on_error(data):
            self.progress_signal.emit(data)
        
        def on_cancelled(data):
            self.progress_signal.emit(data)
        
        callbacks = {
            EventType.PROGRESS: on_progress,
            EventType.COMPLETED: on_completed,
            EventType.ERROR: on_error,
            EventType.CANCELLED: on_cancelled,
            EventType.PAUSED: on_progress,
            EventType.RESUMED: on_progress,
        }
        
        handles = [self.manager.events.on(e, cb) for e, cb in callbacks.items()]
        
        while self.running:
            self.msleep(100)
        
        for h in handles:
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = DownloadManager()
        self.task_rows = {}
        self.task_types = {}
        
        self.init_ui()
        self.setup_events()
        
    def init_ui(self):
        self.setWindowTitle("Download Manager Pro")
        self.setMinimumSize(900, 550)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Введите URL для загрузки (видео или файл)...")
        self.url_input.returnPressed.connect(self.handle_add_download)
        
        self.detect_label = QLabel()
        self.detect_label.setStyleSheet("color: #666; padding: 0 5px;")
        
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.clicked.connect(self.browse_folder)
        
        self.add_btn = QPushButton("Скачать")
        self.add_btn.clicked.connect(self.handle_add_download)
        
        url_layout.addWidget(self.url_input, 1)
        url_layout.addWidget(self.detect_label)
        url_layout.addWidget(self.browse_btn)
        url_layout.addWidget(self.add_btn)
        layout.addLayout(url_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Название", "URL", "Размер", "Загружено", "Прогресс", "Статус", "Тип"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(6, True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        controls_layout = QHBoxLayout()
        
        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.clicked.connect(self.pause_selected)
        self.pause_btn.setEnabled(False)
        
        self.resume_btn = QPushButton("▶ Продолжить")
        self.resume_btn.clicked.connect(self.resume_selected)
        self.resume_btn.setEnabled(False)
        
        self.cancel_btn = QPushButton("✖ Отмена")
        self.cancel_btn.clicked.connect(self.cancel_selected)
        self.cancel_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self.clear_completed)
        
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.resume_btn)
        controls_layout.addWidget(self.cancel_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.clear_btn)
        layout.addLayout(controls_layout)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        
        settings_action = QAction("Настройки...", self)
        settings_action.triggered.connect(self.show_settings)
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        help_menu = menubar.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_events(self):
        self.progress_emitter = ProgressEmitter(self.manager)
        self.progress_emitter.progress_signal.connect(self.on_progress)
        self.progress_emitter.start()
        
        self.url_input.textChanged.connect(self.on_url_changed)
    
    def on_url_changed(self, text):
        if URLParser.is_supported_video(text):
            platform = URLParser.get_platform_name(text)
            self.detect_label.setText(f"🎬 {platform}")
        elif URLParser.is_valid_url(text):
            self.detect_label.setText("📁 Файл")
        else:
            self.detect_label.setText("")
    
    def on_selection_changed(self):
        selected = self.table.selectedIndexes()
        has_selection = len(selected) > 0
        self.pause_btn.setEnabled(has_selection)
        self.resume_btn.setEnabled(has_selection)
        self.cancel_btn.setEnabled(has_selection)
    
    def handle_add_download(self):
        url = self.url_input.text().strip()
        if not url:
            return
        
        if URLParser.is_supported_video(url):
            self.add_video_download(url)
        else:
            self.add_http_download(url)
    
    def add_video_download(self, url: str):
        self.status_bar.showMessage("Получение информации о видео...")
        self.add_btn.setEnabled(False)
        
        def fetch_info():
            success, info, error = VideoInfoExtractor.get_video_info(url)
            
            def on_result():
                self.add_btn.setEnabled(True)
                self.status_bar.clearMessage()
                
                if not success or not info:
                    QMessageBox.warning(self, "Ошибка", error or "Не удалось получить информацию")
                    return
                
                dialog = FormatDialog(info, self)
                if dialog.exec():
                    fmt, quality = dialog.get_selection()
                    
                    task_id = self.manager.add_video_download(
                        url,
                        speed_limit=0,
                        video_format=fmt,
                        video_quality=quality
                    )
                    self.url_input.clear()
                    self.status_bar.showMessage(f"Добавлено: {info.title[:50]}...")
            
            QTimer.singleShot(0, on_result)
        
        Thread(target=fetch_info, daemon=True).start()
    
    def add_http_download(self, url: str):
        try:
            task_id = self.manager.add_download(url)
            self.url_input.clear()
            self.status_bar.showMessage("Загрузка добавлена")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
    
    def on_progress(self, data):
        task_id = data["id"]
        
        if task_id not in self.task_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.task_rows[task_id] = row
            
            title = data.get("title", data.get("url", "").split("/")[-1][:30])
            title_item = QTableWidgetItem(title)
            title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, title_item)
            
            url_item = QTableWidgetItem(data.get("url", ""))
            url_item.setFlags(url_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, url_item)
            
            type_item = QTableWidgetItem(data.get("type", "http"))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 6, type_item)
            
            self.task_types[task_id] = data.get("type", "http")
        
        row = self.task_rows[task_id]
        
        total = data.get("total", 0)
        downloaded = data.get("downloaded", 0)
        
        total_item = self.table.item(row, 2)
        if total_item is None:
            total_item = QTableWidgetItem()
            self.table.setItem(row, 2, total_item)
        total_item.setText(self._format_size(total))
        
        downloaded_item = self.table.item(row, 3)
        if downloaded_item is None:
            downloaded_item = QTableWidgetItem()
            self.table.setItem(row, 3, downloaded_item)
        downloaded_item.setText(self._format_size(downloaded))
        
        percent = data.get("percent", 0)
        progress_item = self.table.item(row, 4)
        if progress_item is None:
            progress_item = QTableWidgetItem()
            self.table.setItem(row, 4, progress_item)
        progress_item.setText(f"{percent:.1f}%")
        
        status_map = {
            "pending": "⏳ Ожидание",
            "extracting": "🔍 Поиск...",
            "processing": "⚙️ Обработка",
            "downloading": f"⬇️ {percent:.0f}%",
            "paused": "⏸️ Пауза",
            "completed": "✅ Готово",
            "cancelled": "❌ Отменено",
            "error": f"❌ Ошибка"
        }
        
        status = data.get("status", "downloading")
        status_item = self.table.item(row, 5)
        if status_item is None:
            status_item = QTableWidgetItem()
            self.table.setItem(row, 5, status_item)
        status_item.setText(status_map.get(status, status))
        
        if status == "completed":
            self.status_bar.showMessage(f"Завершено: {data.get('title', data.get('url', ''))[:50]}")
        elif status == "error":
            self.status_bar.showMessage(f"Ошибка: {data.get('error', '')}")
    
    def pause_selected(self):
        row = self._get_selected_row()
        if row is not None:
            task_id = self._row_to_task_id(row)
            if task_id:
                self.manager.pause(task_id)
    
    def resume_selected(self):
        row = self._get_selected_row()
        if row is not None:
            task_id = self._row_to_task_id(row)
            if task_id:
                self.manager.resume(task_id)
    
    def cancel_selected(self):
        row = self._get_selected_row()
        if row is not None:
            task_id = self._row_to_task_id(row)
            if task_id:
                self.manager.cancel(task_id)
    
    def _get_selected_row(self):
        selected = self.table.selectedIndexes()
        if selected:
            return selected[0].row()
        return None
    
    def _row_to_task_id(self, row):
        for tid, r in self.task_rows.items():
            if r == row:
                return tid
        return None
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.manager.set_default_path(folder)
            self.status_bar.showMessage(f"Папка: {folder}")
    
    def clear_completed(self):
        self.manager.cleanup_completed()
        
        rows_to_remove = []
        for task_id, row in list(self.task_rows.items()):
            progress = self.manager.get_progress(task_id)
            if progress is None or progress["status"] in ("completed", "cancelled", "error"):
                rows_to_remove.append(row)
        
        for row in sorted(set(rows_to_remove), reverse=True):
            self.table.removeRow(row)
        
        self.task_rows = {tid: i for tid, i in self.task_rows.items() 
                         if self.table.rowCount() > i}
        
        self.status_bar.showMessage("Очищено")
    
    def show_settings(self):
        QMessageBox.information(self, "Настройки", 
                               "• Максимум 10 одновременных загрузок\n"
                               "• Поддержка YouTube, Vimeo, VK и др.\n"
                               "• Выбор качества и формата видео\n"
                               "• Возобновление загрузок")
    
    def show_about(self):
        QMessageBox.about(self, "О программе",
                         "<b>Download Manager Pro</b><br>"
                         "Версия 1.0<br><br>"
                         "Менеджер загрузок с поддержкой:<br>"
                         "• HTTP/HTTPS файлов<br>"
                         "• YouTube, Vimeo, VK Video<br>"
                         "• SoundCloud, Dailymotion<br><br>"
                         "Использует yt-dlp для видео")
    
    def _format_size(self, bytes_size):
        if not bytes_size:
            return "—"
        for unit in ["Б", "КБ", "МБ", "ГБ"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} ТБ"
    
    def closeEvent(self, event):
        self.progress_emitter.running = False
        self.progress_emitter.wait(500)
        event.accept()


from threading import Thread


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
