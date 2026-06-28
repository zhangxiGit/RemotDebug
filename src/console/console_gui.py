import sys
import threading
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QSpinBox, QStatusBar, QMenu, QAction, QSizePolicy,
    QSplitter, QFrame, QToolBar, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QFont, QIcon

from config.config import AppConfig, load_config, save_config
from src.mqtt.mqtt_client import MQTTClient
from src.utils.logger import setup_logger, LogBuffer
from src.protocol.protocol import (
    TOPIC_A, TOPIC_B,
    CMD_LOG, CMD_STATUS, CMD_HEARTBEAT, CMD_ACK, CMD_EXEC, CMD_CONFIG, CMD_SHELL, CMD_TEST,
    build_message, parse_message, validate_message, build_error_response
)

DARK_STYLE = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: Consolas, Monaco, monospace;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px;
    color: #d4d4d4;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #4a90d9;
}

QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #4c4c4c;
    border-radius: 4px;
    padding: 6px 12px;
    color: #d4d4d4;
}

QPushButton:hover {
    background-color: #4c4c4c;
}

QPushButton:pressed {
    background-color: #5c5c5c;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #666666;
}

QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 8px 0 0;
    color: #858585;
}

QTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    color: #d4d4d4;
    font-family: Consolas, Monaco, monospace;
    font-size: 11pt;
}

QStatusBar {
    background-color: #2d2d2d;
    border-top: 1px solid #3c3c3c;
}

QLabel {
    color: #cccccc;
}

QMenuBar {
    background-color: #2d2d2d;
}

QMenuBar::item {
    background-color: #2d2d2d;
    color: #d4d4d4;
    padding: 4px 12px;
}

QMenuBar::item:selected {
    background-color: #3c3c3c;
}

QMenu {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
}

QMenu::item {
    padding: 4px 24px;
    color: #d4d4d4;
}

QMenu::item:selected {
    background-color: #3c3c3c;
}

QToolBar {
    background-color: #2d2d2d;
    border-bottom: 1px solid #3c3c3c;
}
"""

class ConsoleGUI(QMainWindow):
    log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(bool)
    stats_signal = pyqtSignal(int, int)
    
    def __init__(self):
        super().__init__()
        self.config = load_config('config/console_config.json')
        self.logger = setup_logger(self.config.log)
        self.log_buffer = LogBuffer(max_lines=5000)
        
        self.mqtt_client = None
        self.running = True
        
        self.topic_a = TOPIC_A  # 订阅目标（接收Client消息）
        self.topic_b = TOPIC_B  # 发送目标
        self.username = self.config.mqtt.username
        
        self.message_count = 0
        self.sent_count = 0
        self.connect_time = None
        self.cmd_history = []
        self.cmd_history_index = -1
        
        self.load_cmd_history()
        
        self.init_ui()
        self.log_signal.connect(self.append_log)
        self.status_signal.connect(self.update_status)
        self.stats_signal.connect(self.update_stats)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_connection_time)
        self.timer.start(1000)
    
    def init_ui(self):
        self.setWindowTitle("IoT Remote Debug - Console")
        self.setGeometry(100, 100, 1100, 700)
        self.setStyleSheet(DARK_STYLE)
        
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        
        save_log_action = QAction('Save Log', self)
        save_log_action.triggered.connect(self.save_log_to_file)
        file_menu.addAction(save_log_action)
        
        clear_log_action = QAction('Clear Log', self)
        clear_log_action.triggered.connect(self.clear_log)
        file_menu.addAction(clear_log_action)
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        tool_bar = QToolBar()
        self.addToolBar(tool_bar)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_log)
        tool_bar.addWidget(clear_btn)
        
        tool_bar.addSeparator()
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs...")
        self.filter_input.textChanged.connect(self.filter_logs)
        self.filter_input.setFixedWidth(200)
        tool_bar.addWidget(self.filter_input)
        
        tool_bar.addSeparator()
        
        self.auto_scroll_check = QPushButton("Auto Scroll")
        self.auto_scroll_check.setCheckable(True)
        self.auto_scroll_check.setChecked(True)
        tool_bar.addWidget(self.auto_scroll_check)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(300)
        
        mqtt_group = QGroupBox("MQTT Configuration")
        mqtt_group_layout = QVBoxLayout(mqtt_group)
        mqtt_group_layout.setSpacing(6)
        
        broker_layout = QHBoxLayout()
        broker_layout.addWidget(QLabel("Broker:"))
        self.mqtt_broker = QLineEdit(self.config.mqtt.broker)
        self.mqtt_broker.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        broker_layout.addWidget(self.mqtt_broker)
        mqtt_group_layout.addLayout(broker_layout)
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.mqtt_port = QSpinBox()
        self.mqtt_port.setRange(1, 65535)
        self.mqtt_port.setValue(self.config.mqtt.port)
        self.mqtt_port.setFixedWidth(100)
        port_layout.addWidget(self.mqtt_port)
        mqtt_group_layout.addLayout(port_layout)
        
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("User:"))
        self.mqtt_user = QLineEdit(self.config.mqtt.username)
        self.mqtt_user.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        user_layout.addWidget(self.mqtt_user)
        mqtt_group_layout.addLayout(user_layout)
        
        pass_layout = QHBoxLayout()
        pass_layout.addWidget(QLabel("Pass:"))
        self.mqtt_pass = QLineEdit(self.config.mqtt.password)
        self.mqtt_pass.setEchoMode(QLineEdit.Password)
        self.mqtt_pass.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pass_layout.addWidget(self.mqtt_pass)
        mqtt_group_layout.addLayout(pass_layout)
        
        client_id_layout = QHBoxLayout()
        client_id_layout.addWidget(QLabel("Client ID:"))
        self.mqtt_client_id = QLineEdit(self.config.mqtt.client_id)
        self.mqtt_client_id.setPlaceholderText("Leave empty for auto-generate")
        self.mqtt_client_id.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        client_id_layout.addWidget(self.mqtt_client_id)
        mqtt_group_layout.addLayout(client_id_layout)
        
        self.mqtt_connect_btn = QPushButton("Connect MQTT")
        self.mqtt_connect_btn.clicked.connect(self.connect_mqtt)
        self.mqtt_connect_btn.setStyleSheet("background-color: #0e639c; color: white;")
        mqtt_group_layout.addWidget(self.mqtt_connect_btn)
        
        left_layout.addWidget(mqtt_group)
        
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(6, 6, 6, 6)
        
        self.mqtt_status_label = QLabel("MQTT: Disconnected")
        self.mqtt_status_label.setStyleSheet("color: #ff4757;")
        status_layout.addWidget(self.mqtt_status_label)
        
        left_layout.addWidget(status_frame)
        
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        left_layout.addWidget(save_btn)
        
        left_layout.addStretch()
        
        main_splitter.addWidget(left_panel)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Remote Device Log"))
        self.log_count_label = QLabel("0 messages")
        self.log_count_label.setStyleSheet("color: #858585;")
        log_header.addWidget(self.log_count_label)
        log_header.addStretch()
        right_layout.addLayout(log_header)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.NoWrap)
        right_layout.addWidget(self.log_display)
        
        input_header = QHBoxLayout()
        input_header.addWidget(QLabel("Command Input"))
        input_header.addStretch()
        right_layout.addLayout(input_header)
        
        send_layout = QHBoxLayout()
        self.cmd_select = QComboBox()
        self.cmd_select.addItems(["SHELL", "TEST"])
        self.cmd_select.setFixedWidth(100)
        send_layout.addWidget(self.cmd_select)
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Enter command to send...")
        self.send_input.returnPressed.connect(self.send_command)
        self.send_input.installEventFilter(self)
        send_layout.addWidget(self.send_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_command)
        self.send_btn.setStyleSheet("background-color: #5c5c5c;")
        send_layout.addWidget(self.send_btn)
        right_layout.addLayout(send_layout)
        
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        
        self.setCentralWidget(main_splitter)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.mqtt_status_bar = QLabel("MQTT: Disconnected")
        self.mqtt_status_bar.setStyleSheet("color: #ff4757;")
        self.status_bar.addWidget(self.mqtt_status_bar)
        
        sep1 = QLabel(" | ")
        sep1.setStyleSheet("color: #555555;")
        self.status_bar.addWidget(sep1)
        
        self.connect_time_label = QLabel("Up Time: 00:00:00")
        self.status_bar.addPermanentWidget(self.connect_time_label)
        
        sep3 = QLabel(" | ")
        sep3.setStyleSheet("color: #555555;")
        self.status_bar.addPermanentWidget(sep3)
        
        self.msg_count_label = QLabel("Rx: 0 | Tx: 0")
        self.status_bar.addPermanentWidget(self.msg_count_label)
    
    def eventFilter(self, obj, event):
        if obj == self.send_input and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Up:
                if self.cmd_history and self.cmd_history_index > 0:
                    self.cmd_history_index -= 1
                    self.send_input.setText(self.cmd_history[self.cmd_history_index])
                    return True
            elif event.key() == Qt.Key_Down:
                if self.cmd_history:
                    if self.cmd_history_index < len(self.cmd_history) - 1:
                        self.cmd_history_index += 1
                        self.send_input.setText(self.cmd_history[self.cmd_history_index])
                    else:
                        self.cmd_history_index = len(self.cmd_history)
                        self.send_input.clear()
                    return True
        return super().eventFilter(obj, event)
    
    def load_cmd_history(self):
        try:
            with open('config/console_cmd_history.json', 'r') as f:
                self.cmd_history = json.load(f)
        except:
            self.cmd_history = []
    
    def save_cmd_history(self):
        try:
            with open('config/console_cmd_history.json', 'w') as f:
                json.dump(self.cmd_history[-50:], f)
        except:
            pass
    
    def connect_mqtt(self):
        if self.mqtt_client and self.mqtt_client.connected:
            self.mqtt_client.disconnect()
            self.mqtt_connect_btn.setText("Connect MQTT")
            self.mqtt_connect_btn.setStyleSheet("background-color: #0e639c; color: white;")
            self.log_signal.emit("INFO", "Disconnected from MQTT broker")
            self.status_signal.emit(False)
            return
        
        self.config.mqtt.broker = self.mqtt_broker.text()
        self.config.mqtt.port = self.mqtt_port.value()
        self.config.mqtt.username = self.mqtt_user.text()
        self.config.mqtt.password = self.mqtt_pass.text()
        self.config.mqtt.client_id = self.mqtt_client_id.text().strip()
        self.username = self.config.mqtt.username
        
        self.mqtt_client = MQTTClient(self.config.mqtt)
        self.mqtt_client.on_connect_callback = self.on_mqtt_connect
        self.mqtt_client.on_message_callback = self.on_mqtt_message
        
        self.log_signal.emit("INFO", f"Connecting to MQTT: {self.config.mqtt.broker}:{self.config.mqtt.port}...")
        self.mqtt_connect_btn.setEnabled(False)
        self.mqtt_connect_btn.setText("Connecting...")
        
        threading.Thread(target=self.mqtt_client.connect, daemon=True).start()
    
    def on_mqtt_connect(self, success):
        if success:
            self.mqtt_connect_btn.setText("Disconnect MQTT")
            self.mqtt_connect_btn.setStyleSheet("background-color: #c74440; color: white;")
            self.log_signal.emit("SUCCESS", "MQTT connection established")
            # 连接成功后自动订阅 Topic A
            self.mqtt_client.subscribe(self.topic_a)
            self.log_signal.emit("INFO", f"Subscribed to: {self.topic_a}")
            self.status_signal.emit(True)
            self.connect_time = datetime.now()
        else:
            self.log_signal.emit("ERROR", "MQTT connection failed")
            self.status_signal.emit(False)
        self.mqtt_connect_btn.setEnabled(True)
    
    def on_mqtt_message(self, topic, payload):
        # 只处理订阅的 Topic A 消息
        if topic != self.topic_a:
            return
        
        # 使用 parse_message 解析 JSON
        msg = parse_message(payload)
        if msg is None:
            self.log_signal.emit("ERROR", "消息解析失败：非合法 JSON 格式")
            return
        
        # 使用 validate_message 校验消息
        valid, error = validate_message(msg)
        if not valid:
            # 校验失败，使用 build_error_response 构建错误消息，发送到 Topic B
            ref_msg_id = msg.get("MSG_ID", "") if isinstance(msg, dict) else ""
            try:
                error_response = build_error_response(self.username, ref_msg_id, error)
                if self.mqtt_client and self.mqtt_client.connected:
                    self.mqtt_client.publish(self.topic_b, error_response.encode('utf-8'))
            except Exception as e:
                self.log_signal.emit("ERROR", f"构建错误响应失败: {str(e)}")
            self.log_signal.emit("ERROR", f"消息校验失败: {error}")
            return
        
        # 校验通过，提取字段
        username = msg.get("USERNAME", "")
        cmd = msg.get("CMD", "")
        data = msg.get("DATA", "")
        
        # DATA 可能是 dict/list/str 等类型，统一转为字符串展示
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # 按 [USERNAME] [CMD] [DATA] 格式打印到日志区
        log_text = f"[{username}] [{cmd}] {data_str}"
        
        # 按 CMD 类型分别处理
        if cmd == CMD_LOG:
            # Client 上报日志
            self.log_signal.emit("LOG", log_text)
            self.log_buffer.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_text}")
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
        elif cmd == CMD_STATUS:
            # Client 上报设备状态
            self.log_signal.emit("STATUS", log_text)
            self.log_buffer.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_text}")
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
        elif cmd == CMD_HEARTBEAT:
            # 心跳保活，可忽略或显示心跳信息
            self.log_signal.emit("HEARTBEAT", log_text)
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
        elif cmd == CMD_ACK:
            # 确认回执
            self.log_signal.emit("ACK", log_text)
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
        elif cmd == CMD_TEST:
            # TEST 命令响应（来自Client端）
            self.log_signal.emit("TEST", log_text)
            self.log_buffer.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_text}")
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
        else:
            # 其他未知 CMD，按通用日志处理
            self.log_signal.emit("LOG", log_text)
            self.log_buffer.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_text}")
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
    
    def send_command(self):
        # 输入框内容作为 DATA 字段
        cmd_text = self.send_input.text().strip()
        if not cmd_text:
            return
        
        if not self.mqtt_client or not self.mqtt_client.connected:
            self.log_signal.emit("ERROR", "MQTT not connected")
            return
        
        # 获取 CMD 下拉框选择的 CMD 值（EXEC 或 CONFIG）
        cmd = self.cmd_select.currentText()
        
        # 使用 build_message 封装为 JSON 消息，USERNAME 使用 MQTT 配置的 username
        message = build_message(self.username, cmd, cmd_text)
        
        self.log_signal.emit("CMD", f"Sent [{cmd}]: {cmd_text}")
        
        # 发送到 Topic B
        success = self.mqtt_client.publish(self.topic_b, message.encode('utf-8'))
        if success:
            self.sent_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count)
            
            # 保留指令历史记录功能
            if cmd_text not in self.cmd_history:
                self.cmd_history.append(cmd_text)
                self.save_cmd_history()
            self.cmd_history_index = len(self.cmd_history)
        else:
            self.log_signal.emit("ERROR", "Failed to send command")
        
        self.send_input.clear()
    
    def append_log(self, log_type, text):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        color_map = {
            "INFO": "#858585",
            "SUCCESS": "#4ec9b0",
            "ERROR": "#ff4757",
            "CMD": "#dcdcaa",
            "LOG": "#9cdcfe",
            "STATUS": "#c586c0",
            "HEARTBEAT": "#ce9178",
            "ACK": "#6a9955",
            "TEST": "#4fc1ff"
        }
        
        color = color_map.get(log_type, "#d4d4d4")
        
        self.log_display.setTextColor(QColor(color))
        self.log_display.append(f"[{timestamp}] [{log_type}] {text}")
        self.log_display.setTextColor(QColor("#d4d4d4"))
        
        if self.auto_scroll_check.isChecked():
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_display.setTextCursor(cursor)
        
        self.log_count_label.setText(f"{self.message_count + self.sent_count} messages")
    
    def filter_logs(self, filter_text):
        pass
    
    def update_status(self, connected):
        if connected:
            self.mqtt_status_label.setText("MQTT: Connected")
            self.mqtt_status_label.setStyleSheet("color: #4ec9b0;")
            self.mqtt_status_bar.setText("MQTT: Connected")
            self.mqtt_status_bar.setStyleSheet("color: #4ec9b0;")
        else:
            self.mqtt_status_label.setText("MQTT: Disconnected")
            self.mqtt_status_label.setStyleSheet("color: #ff4757;")
            self.mqtt_status_bar.setText("MQTT: Disconnected")
            self.mqtt_status_bar.setStyleSheet("color: #ff4757;")
            self.connect_time = None
    
    def update_stats(self, rx_count, tx_count):
        self.msg_count_label.setText(f"Rx: {rx_count} | Tx: {tx_count}")
    
    def update_connection_time(self):
        if self.connect_time:
            elapsed = datetime.now() - self.connect_time
            hours = elapsed.seconds // 3600
            minutes = (elapsed.seconds % 3600) // 60
            seconds = elapsed.seconds % 60
            self.connect_time_label.setText(f"Up Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def save_log_to_file(self):
        logs = self.log_buffer.get_all()
        if not logs:
            self.log_signal.emit("INFO", "No logs to save")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", f"console_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(logs))
                self.log_signal.emit("SUCCESS", f"Log saved to: {file_path}")
            except Exception as e:
                self.log_signal.emit("ERROR", f"Failed to save log: {str(e)}")
    
    def clear_log(self):
        self.log_display.clear()
        self.log_buffer.clear()
        self.message_count = 0
        self.sent_count = 0
        self.log_count_label.setText("0 messages")
        self.msg_count_label.setText("Rx: 0 | Tx: 0")
        self.log_signal.emit("INFO", "Log cleared")
    
    def save_config(self):
        save_config(self.config, 'config/console_config.json')
        self.log_signal.emit("SUCCESS", "Configuration saved")
    
    def closeEvent(self, event):
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = ConsoleGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
