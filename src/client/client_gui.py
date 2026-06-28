import sys
import threading
import time
import json
import socket
import urllib.request
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QSpinBox, QStatusBar, QTabWidget, QMenu, QAction, QSizePolicy,
    QSplitter, QFrame, QToolBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from PyQt5.QtGui import QTextCursor, QColor, QFont, QIcon

from config.config import AppConfig, load_config, save_config
from src.mqtt.mqtt_client import MQTTClient
from src.comm.communication import SerialInterface, HIDInterface
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

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-bottom: none;
    padding: 6px 12px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-color: #4a90d9;
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

class ClientGUI(QMainWindow):
    log_signal = pyqtSignal(str, str)
    serial_log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(bool, str)
    stats_signal = pyqtSignal(int, int, int)
    
    def __init__(self):
        super().__init__()
        self.config = load_config('config/client_config.json')
        self.logger = setup_logger(self.config.log)
        self.log_buffer = LogBuffer(max_lines=5000)
        
        self.mqtt_client = None
        self.comm_interface = None
        self.comm_thread = None
        self.running = True
        
        self.device_id = "client_001"
        self.topic_a = TOPIC_A  # 发送目标
        self.topic_b = TOPIC_B  # 订阅目标
        self.username = self.config.mqtt.username

        self.message_count = 0
        self.sent_count = 0
        self.connect_time = None

        self.init_ui()
        self.log_signal.connect(self.append_log)
        self.serial_log_signal.connect(self.append_serial_log)
        self.status_signal.connect(self.update_status)
        self.stats_signal.connect(self.update_stats)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_connection_time)
        self.timer.start(1000)
    
    def init_ui(self):
        self.setWindowTitle(f"IoT Remote Debug - Client ({self.device_id})")
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
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(320)
        
        self.tab_widget = QTabWidget()
        
        mqtt_tab = QWidget()
        mqtt_layout = QVBoxLayout(mqtt_tab)
        mqtt_layout.setContentsMargins(8, 8, 8, 8)
        mqtt_layout.setSpacing(8)
        
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
        
        mqtt_layout.addWidget(mqtt_group)
        
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(6, 6, 6, 6)
        
        self.mqtt_status_label = QLabel("MQTT: Disconnected")
        self.mqtt_status_label.setStyleSheet("color: #ff4757;")
        status_layout.addWidget(self.mqtt_status_label)
        
        self.device_status_label = QLabel("Device: Disconnected")
        self.device_status_label.setStyleSheet("color: #ff4757;")
        status_layout.addWidget(self.device_status_label)
        
        mqtt_layout.addWidget(status_frame)
        
        self.tab_widget.addTab(mqtt_tab, "MQTT")
        
        comm_tab = QWidget()
        comm_layout = QVBoxLayout(comm_tab)
        comm_layout.setContentsMargins(8, 8, 8, 8)
        comm_layout.setSpacing(8)
        
        comm_type_layout = QHBoxLayout()
        comm_type_layout.addWidget(QLabel("Interface:"))
        self.comm_type = QComboBox()
        self.comm_type.addItems(["Serial", "USB HID"])
        self.comm_type.currentIndexChanged.connect(self.update_comm_settings)
        comm_type_layout.addWidget(self.comm_type)
        comm_layout.addLayout(comm_type_layout)
        
        self.serial_group = QGroupBox("Serial Port")
        serial_layout = QVBoxLayout(self.serial_group)
        serial_layout.setSpacing(6)
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.serial_port = QComboBox()
        self.refresh_ports_btn = QPushButton("Refresh")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        self.refresh_ports_btn.setFixedWidth(70)
        port_layout.addWidget(self.serial_port)
        port_layout.addWidget(self.refresh_ports_btn)
        serial_layout.addLayout(port_layout)
        
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("Baud:"))
        self.serial_baud = QComboBox()
        self.serial_baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800"])
        self.serial_baud.setCurrentText(str(self.config.serial.baud_rate))
        self.serial_baud.setFixedWidth(120)
        baud_layout.addWidget(self.serial_baud)
        
        data_bits_layout = QHBoxLayout()
        data_bits_layout.addWidget(QLabel("Data:"))
        self.serial_data = QComboBox()
        self.serial_data.addItems(["5", "6", "7", "8"])
        self.serial_data.setCurrentText(str(self.config.serial.data_bits))
        self.serial_data.setFixedWidth(60)
        data_bits_layout.addWidget(self.serial_data)
        baud_layout.addLayout(data_bits_layout)
        serial_layout.addLayout(baud_layout)
        
        parity_stop_layout = QHBoxLayout()
        parity_stop_layout.addWidget(QLabel("Parity:"))
        self.serial_parity = QComboBox()
        self.serial_parity.addItems(["N", "O", "E"])
        self.serial_parity.setCurrentText(self.config.serial.parity)
        self.serial_parity.setFixedWidth(60)
        parity_stop_layout.addWidget(self.serial_parity)
        
        parity_stop_layout.addWidget(QLabel("Stop:"))
        self.serial_stop = QComboBox()
        self.serial_stop.addItems(["1", "1.5", "2"])
        self.serial_stop.setCurrentText(str(self.config.serial.stop_bits))
        self.serial_stop.setFixedWidth(60)
        parity_stop_layout.addWidget(self.serial_stop)
        serial_layout.addLayout(parity_stop_layout)
        
        comm_layout.addWidget(self.serial_group)
        
        self.hid_group = QGroupBox("USB HID")
        hid_layout = QVBoxLayout(self.hid_group)
        hid_layout.setSpacing(6)
        
        vid_layout = QHBoxLayout()
        vid_layout.addWidget(QLabel("Vendor ID:"))
        self.hid_vid = QLineEdit(f"0x{self.config.hid.vendor_id:04X}")
        vid_layout.addWidget(self.hid_vid)
        hid_layout.addLayout(vid_layout)
        
        pid_layout = QHBoxLayout()
        pid_layout.addWidget(QLabel("Product ID:"))
        self.hid_pid = QLineEdit(f"0x{self.config.hid.product_id:04X}")
        pid_layout.addWidget(self.hid_pid)
        hid_layout.addLayout(pid_layout)
        
        self.refresh_hid_btn = QPushButton("Refresh Devices")
        self.refresh_hid_btn.clicked.connect(self.refresh_hid_devices)
        hid_layout.addWidget(self.refresh_hid_btn)
        
        self.hid_device_list = QComboBox()
        hid_layout.addWidget(self.hid_device_list)
        
        comm_layout.addWidget(self.hid_group)
        self.hid_group.setVisible(False)
        
        self.comm_connect_btn = QPushButton("Connect Device")
        self.comm_connect_btn.clicked.connect(self.connect_device)
        self.comm_connect_btn.setStyleSheet("background-color: #2d5a27; color: white;")
        comm_layout.addWidget(self.comm_connect_btn)
        
        self.tab_widget.addTab(comm_tab, "Device")
        
        left_layout.addWidget(self.tab_widget)
        
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        left_layout.addWidget(save_btn)
        
        left_layout.addStretch()
        
        main_splitter.addWidget(left_panel)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 垂直分割器，上面MQTT日志，下面串口日志
        log_splitter = QSplitter(Qt.Vertical)
        
        # MQTT 日志区域
        mqtt_log_widget = QWidget()
        mqtt_log_layout = QVBoxLayout(mqtt_log_widget)
        mqtt_log_layout.setContentsMargins(0, 0, 0, 0)
        
        mqtt_log_header = QHBoxLayout()
        mqtt_log_header.addWidget(QLabel("MQTT Log"))
        self.log_count_label = QLabel("0 messages")
        self.log_count_label.setStyleSheet("color: #858585;")
        mqtt_log_header.addWidget(self.log_count_label)
        mqtt_log_header.addStretch()
        mqtt_log_layout.addLayout(mqtt_log_header)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.NoWrap)
        mqtt_log_layout.addWidget(self.log_display)
        
        log_splitter.addWidget(mqtt_log_widget)
        
        # 串口/USB 日志区域
        serial_log_widget = QWidget()
        serial_log_layout = QVBoxLayout(serial_log_widget)
        serial_log_layout.setContentsMargins(0, 0, 0, 0)
        
        serial_log_header = QHBoxLayout()
        serial_log_header.addWidget(QLabel("Serial / USB HID Log"))
        serial_log_header.addStretch()
        serial_log_layout.addLayout(serial_log_header)
        
        self.serial_log_display = QTextEdit()
        self.serial_log_display.setReadOnly(True)
        self.serial_log_display.setLineWrapMode(QTextEdit.NoWrap)
        serial_log_layout.addWidget(self.serial_log_display)
        
        log_splitter.addWidget(serial_log_widget)
        
        log_splitter.setStretchFactor(0, 3)
        log_splitter.setStretchFactor(1, 2)
        
        right_layout.addWidget(log_splitter)

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
        
        self.device_status_bar = QLabel("Device: Disconnected")
        self.device_status_bar.setStyleSheet("color: #ff4757;")
        self.status_bar.addWidget(self.device_status_bar)
        
        sep2 = QLabel(" | ")
        sep2.setStyleSheet("color: #555555;")
        self.status_bar.addWidget(sep2)
        
        self.connect_time_label = QLabel("Up Time: 00:00:00")
        self.status_bar.addPermanentWidget(self.connect_time_label)
        
        sep3 = QLabel(" | ")
        sep3.setStyleSheet("color: #555555;")
        self.status_bar.addPermanentWidget(sep3)
        
        self.msg_count_label = QLabel("Rx: 0 | Tx: 0")
        self.status_bar.addPermanentWidget(self.msg_count_label)
        
        self.refresh_serial_ports()
    
    def update_comm_settings(self, index):
        if index == 0:
            self.serial_group.setVisible(True)
            self.hid_group.setVisible(False)
        else:
            self.serial_group.setVisible(False)
            self.hid_group.setVisible(True)
            self.refresh_hid_devices()
    
    def refresh_serial_ports(self):
        self.serial_port.clear()
        ports = SerialInterface.list_ports()
        for port in ports:
            self.serial_port.addItem(f"{port['port']} - {port['description']}", port['port'])
    
    def refresh_hid_devices(self):
        self.hid_device_list.clear()
        devices = HIDInterface.list_devices()
        for device in devices:
            vid = device['vendor_id']
            pid = device['product_id']
            name = device.get('product_string', f"Unknown Device")
            self.hid_device_list.addItem(f"{name} (0x{vid:04X}:0x{pid:04X})", (vid, pid))
    
    def connect_mqtt(self):
        if self.mqtt_client and self.mqtt_client.connected:
            self.mqtt_client.disconnect()
            self.mqtt_connect_btn.setText("Connect MQTT")
            self.mqtt_connect_btn.setStyleSheet("background-color: #0e639c; color: white;")
            self.log_signal.emit("INFO", "Disconnected from MQTT broker")
            self.status_signal.emit(False, "mqtt")
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
            # 连接成功后自动订阅 Topic B，接收 Console 消息
            self.mqtt_client.subscribe(self.topic_b)
            self.mqtt_connect_btn.setText("Disconnect MQTT")
            self.mqtt_connect_btn.setStyleSheet("background-color: #c74440; color: white;")
            self.log_signal.emit("SUCCESS", "MQTT connection established")
            self.status_signal.emit(True, "mqtt")
            self.connect_time = datetime.now()
        else:
            self.log_signal.emit("ERROR", "MQTT connection failed")
            self.status_signal.emit(False, "mqtt")
        self.mqtt_connect_btn.setEnabled(True)
    
    def on_mqtt_message(self, topic, payload):
        # 仅处理订阅的 Topic B 消息
        if topic != self.topic_b:
            return

        # 解析 JSON 消息
        msg = parse_message(payload)
        if msg is None:
            self.log_signal.emit("ERROR", "消息解析失败：非合法 JSON 格式")
            return

        # 校验消息
        valid, err = validate_message(msg)
        if not valid:
            # 校验失败，构建错误响应发送到 Topic A
            ref_msg_id = msg.get("MSG_ID", "") if isinstance(msg, dict) else ""
            self.log_signal.emit("ERROR", f"消息校验失败: {err}")
            if self.mqtt_client and self.mqtt_client.connected:
                error_resp = build_error_response(self.username, ref_msg_id, err)
                self.mqtt_client.publish(self.topic_a, error_resp.encode('utf-8'))
            return

        username = msg.get("USERNAME", "")
        cmd = msg.get("CMD", "")
        data = msg.get("DATA")

        # 将 DATA 转为字符串用于显示
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, ensure_ascii=False)

        # 按 [USERNAME] [CMD] [DATA] 格式打印到日志区
        self.log_signal.emit("CMD", f"[{username}] [{cmd}] [{data_str}]")
        self.log_buffer.add(f"[CMD] [{username}] [{cmd}] [{data_str}]")

        # 如果是 SHELL，将 DATA 内容转发到 USB/串口设备
        if cmd == CMD_SHELL:
            if self.comm_interface and self.comm_interface.is_connected():
                if isinstance(data, str):
                    send_bytes = data.encode('utf-8')
                else:
                    send_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
                # 自动追加 \r\n 结尾，设备端串口按行解析
                if not send_bytes.endswith(b'\r\n') and not send_bytes.endswith(b'\n') and not send_bytes.endswith(b'\r'):
                    send_bytes += b'\r\n'
                self.comm_interface.send(send_bytes)
                self.sent_count += 1
                self.stats_signal.emit(self.message_count, self.sent_count, 0)
            else:
                self.log_signal.emit("ERROR", "设备未连接，无法转发指令")

        # 如果是 TEST，处理测试子命令（不涉及串口转发）
        elif cmd == CMD_TEST:
            self.handle_test_command(data, username)

    # ==================== TEST 子命令处理 ====================

    def handle_test_command(self, data, requester):
        """处理来自 Console 的 TEST 命令，支持多个子命令。"""
        # 提取子命令字符串
        if isinstance(data, str):
            sub_cmd = data.strip().lower()
        elif isinstance(data, dict):
            sub_cmd = str(data.get("sub_cmd", "")).strip().lower()
        else:
            sub_cmd = str(data).strip().lower()

        # 子命令分发表
        handlers = {
            "help": self._test_help,
            "location": self._test_location,
            "netinfo": self._test_netinfo,
            "auth": self._test_auth,
            "status": self._test_status,
            "uptime": self._test_uptime,
            "disconnect_mqtt": self._test_disconnect_mqtt,
            "reconnect_mqtt": self._test_reconnect_mqtt,
        }

        handler = handlers.get(sub_cmd)
        if handler:
            result = handler()
        else:
            result = f"[ERROR] 未知子命令: '{sub_cmd}'。输入 'help' 查看可用命令。"

        # 将结果通过 TEST 消息回传给 Console
        if self.mqtt_client and self.mqtt_client.connected:
            resp = build_message(self.username, CMD_TEST, result)
            self.mqtt_client.publish(self.topic_a, resp.encode('utf-8'))
            self.message_count += 1
            self.stats_signal.emit(self.message_count, self.sent_count, 0)

        self.log_signal.emit("CMD", f"[TEST] {requester} -> {sub_cmd}")

    def _test_help(self):
        """返回可用子命令列表。"""
        return (
            "=== TEST 子命令列表 ===\n"
            "  help            - 显示本帮助信息\n"
            "  location        - 查询Client端地理位置（基于公网IP）\n"
            "  netinfo         - 查询网络信息（主机名、本地IP、公网IP）\n"
            "  auth            - 查询MQTT用户名和密码\n"
            "  status          - 查询Client端运行状态\n"
            "  uptime          - 查询Client运行时长\n"
            "  disconnect_mqtt - 控制命令：断开MQTT连接\n"
            "  reconnect_mqtt  - 控制命令：重新连接MQTT"
        )

    def _test_location(self):
        """通过公网IP查询地理位置。"""
        try:
            url = "http://ip-api.com/json/?lang=zh-CN"
            req = urllib.request.Request(url, headers={"User-Agent": "IoTDebugClient/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                info = json.loads(resp.read().decode("utf-8"))
            if info.get("status") == "success":
                return (
                    f"=== Client端位置信息 ===\n"
                    f"  国家: {info.get('country', 'N/A')}\n"
                    f"  地区: {info.get('regionName', 'N/A')}\n"
                    f"  城市: {info.get('city', 'N/A')}\n"
                    f"  ISP: {info.get('isp', 'N/A')}\n"
                    f"  经度: {info.get('lon', 'N/A')}\n"
                    f"  纬度: {info.get('lat', 'N/A')}\n"
                    f"  公网IP: {info.get('query', 'N/A')}"
                )
            else:
                return f"[ERROR] 位置查询失败: {info.get('message', '未知错误')}"
        except Exception as e:
            return f"[ERROR] 位置查询异常: {str(e)}"

    def _test_netinfo(self):
        """查询本机网络信息。"""
        try:
            hostname = socket.gethostname()
            # 获取所有本地IP地址
            try:
                local_ips = socket.gethostbyname_ex(hostname)[2]
            except Exception:
                local_ips = [socket.gethostbyname(hostname)]
            # 获取公网IP
            public_ip = "N/A"
            try:
                url = "http://httpbin.org/ip"
                req = urllib.request.Request(url, headers={"User-Agent": "IoTDebugClient/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    public_ip = json.loads(resp.read().decode("utf-8")).get("origin", "N/A")
            except Exception:
                pass
            return (
                f"=== Client端网络信息 ===\n"
                f"  主机名: {hostname}\n"
                f"  本地IP: {', '.join(local_ips)}\n"
                f"  公网IP: {public_ip}"
            )
        except Exception as e:
            return f"[ERROR] 网络信息查询异常: {str(e)}"

    def _test_auth(self):
        """返回当前MQTT认证信息。"""
        return (
            f"=== Client端MQTT认证信息 ===\n"
            f"  Broker: {self.config.mqtt.broker}:{self.config.mqtt.port}\n"
            f"  Username: {self.config.mqtt.username}\n"
            f"  Password: {self.config.mqtt.password}\n"
            f"  ClientID: {self.config.mqtt.client_id or '(自动生成)'}"
        )

    def _test_status(self):
        """返回Client端运行状态。"""
        mqtt_status = "已连接" if (self.mqtt_client and self.mqtt_client.connected) else "未连接"
        device_status = "已连接" if (self.comm_interface and self.comm_interface.is_connected()) else "未连接"
        uptime_str = self._format_uptime()
        return (
            f"=== Client端运行状态 ===\n"
            f"  MQTT连接: {mqtt_status}\n"
            f"  设备连接: {device_status}\n"
            f"  运行时长: {uptime_str}\n"
            f"  接收消息数: {self.message_count}\n"
            f"  发送消息数: {self.sent_count}"
        )

    def _test_uptime(self):
        """返回Client运行时长。"""
        return f"Client运行时长: {self._format_uptime()}"

    def _test_disconnect_mqtt(self):
        """控制命令：断开MQTT连接。"""
        if self.mqtt_client and self.mqtt_client.connected:
            # 通过信号触发UI线程断开
            self.log_signal.emit("INFO", "远程指令：断开MQTT连接")
            # 延迟执行断开，先回复消息
            QTimer.singleShot(100, self._do_disconnect_mqtt)
            return "MQTT连接正在断开..."
        return "MQTT未连接，无需断开"

    def _test_reconnect_mqtt(self):
        """控制命令：重新连接MQTT。"""
        if self.mqtt_client and self.mqtt_client.connected:
            return "MQTT已连接，如需重连请先断开"
        self.log_signal.emit("INFO", "远程指令：重新连接MQTT")
        QTimer.singleShot(100, self._do_reconnect_mqtt)
        return "MQTT正在重新连接..."

    def _do_disconnect_mqtt(self):
        """实际执行MQTT断开。"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
            self.mqtt_connect_btn.setText("Connect MQTT")
            self.mqtt_connect_btn.setStyleSheet("background-color: #0e639c; color: white;")
            self.status_signal.emit(False, "mqtt")

    def _do_reconnect_mqtt(self):
        """实际执行MQTT重连。"""
        if self.mqtt_client:
            self.mqtt_connect_btn.setEnabled(False)
            self.mqtt_connect_btn.setText("Connecting...")
            threading.Thread(target=self.mqtt_client.connect, daemon=True).start()

    def _format_uptime(self):
        """格式化运行时长。"""
        if not self.connect_time:
            return "N/A"
        delta = datetime.now() - self.connect_time
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def connect_device(self):
        if self.comm_interface and self.comm_interface.is_connected():
            self.comm_interface.disconnect()
            self.comm_connect_btn.setText("Connect Device")
            self.comm_connect_btn.setStyleSheet("background-color: #2d5a27; color: white;")
            self.log_signal.emit("INFO", "Disconnected from device")
            self.status_signal.emit(False, "device")
            return
        
        if self.comm_type.currentIndex() == 0:
            port_data = self.serial_port.currentData()
            if not port_data:
                self.log_signal.emit("ERROR", "Please select a serial port")
                return
            
            self.config.serial.port = port_data
            self.config.serial.baud_rate = int(self.serial_baud.currentText())
            self.config.serial.data_bits = int(self.serial_data.currentText())
            self.config.serial.parity = self.serial_parity.currentText()
            self.config.serial.stop_bits = float(self.serial_stop.currentText())
            
            self.comm_interface = SerialInterface(
                port=self.config.serial.port,
                baud_rate=self.config.serial.baud_rate,
                data_bits=self.config.serial.data_bits,
                parity=self.config.serial.parity,
                stop_bits=self.config.serial.stop_bits
            )
        else:
            device_data = self.hid_device_list.currentData()
            if not device_data:
                self.log_signal.emit("ERROR", "Please select an HID device")
                return
            
            vid, pid = device_data
            self.comm_interface = HIDInterface(vendor_id=vid, product_id=pid)
        
        if self.comm_interface.connect():
            self.comm_connect_btn.setText("Disconnect Device")
            self.comm_connect_btn.setStyleSheet("background-color: #c74440; color: white;")
            self.log_signal.emit("SUCCESS", "Device connected successfully")
            self.status_signal.emit(True, "device")
            
            self.comm_thread = threading.Thread(target=self.comm_read_loop, daemon=True)
            self.comm_thread.start()
        else:
            self.log_signal.emit("ERROR", "Failed to connect to device")
    
    def on_device_data(self, data):
        try:
            text = data.decode('utf-8', errors='replace')
            # 在串口日志区显示原始设备日志
            self.serial_log_signal.emit("LOG", text)
            self.log_buffer.add(f"[LOG] {text}")

            # 使用 build_message 封装为 LOG 类型消息，发送到 Topic A
            if self.mqtt_client and self.mqtt_client.connected:
                msg = build_message(self.username, CMD_LOG, text)
                self.mqtt_client.publish(self.topic_a, msg.encode('utf-8'))
                self.message_count += 1
                self.stats_signal.emit(self.message_count, self.sent_count, 0)
        except Exception as e:
            self.serial_log_signal.emit("ERROR", f"数据处理错误: {str(e)}")
    
    def comm_read_loop(self):
        buffer = b""
        last_data_time = 0
        while self.running and self.comm_interface and self.comm_interface.is_connected():
            data = self.comm_interface.receive(1024)
            if data:
                buffer += data
                last_data_time = time.time()

            # 按换行符分割，逐行处理
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                if line.endswith(b"\r"):
                    line = line[:-1]
                self.on_device_data(line)

            # 无换行符回退：超过 200ms 没有新数据且缓冲区有内容，强制分割一帧
            if buffer and (time.time() - last_data_time) > 0.2:
                self.on_device_data(buffer)
                buffer = b""
                last_data_time = time.time()

            time.sleep(0.001)
    
    def append_log(self, log_type, text):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        color_map = {
            "INFO": "#858585",
            "SUCCESS": "#4ec9b0",
            "ERROR": "#ff4757",
            "CMD": "#dcdcaa",
            "LOG": "#9cdcfe"
        }
        
        color = color_map.get(log_type, "#d4d4d4")
        
        self.log_display.setTextColor(QColor(color))
        self.log_display.append(f"[{timestamp}] [{log_type}] {text}")
        self.log_display.setTextColor(QColor("#d4d4d4"))
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_display.setTextCursor(cursor)
        
        self.log_count_label.setText(f"{self.message_count + self.sent_count} messages")
    
    def append_serial_log(self, log_type, text):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        color_map = {
            "LOG": "#9cdcfe",
            "ERROR": "#ff4757",
        }
        
        color = color_map.get(log_type, "#d4d4d4")
        
        self.serial_log_display.setTextColor(QColor(color))
        self.serial_log_display.append(f"[{timestamp}] [{log_type}] {text}")
        self.serial_log_display.setTextColor(QColor("#d4d4d4"))
        
        cursor = self.serial_log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.serial_log_display.setTextCursor(cursor)
    
    def filter_logs(self, filter_text):
        pass
    
    def update_status(self, connected, status_type):
        if status_type == "mqtt":
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
        elif status_type == "device":
            if connected:
                self.device_status_label.setText("Device: Connected")
                self.device_status_label.setStyleSheet("color: #4ec9b0;")
                self.device_status_bar.setText("Device: Connected")
                self.device_status_bar.setStyleSheet("color: #4ec9b0;")
            else:
                self.device_status_label.setText("Device: Disconnected")
                self.device_status_label.setStyleSheet("color: #ff4757;")
                self.device_status_bar.setText("Device: Disconnected")
                self.device_status_bar.setStyleSheet("color: #ff4757;")
    
    def update_stats(self, rx_count, tx_count, _):
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
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"client_log_{timestamp}.txt"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(logs))
            self.log_signal.emit("SUCCESS", f"Log saved to: {file_path}")
        except Exception as e:
            self.log_signal.emit("ERROR", f"Failed to save log: {str(e)}")
    
    def clear_log(self):
        self.log_display.clear()
        self.serial_log_display.clear()
        self.log_buffer.clear()
        self.message_count = 0
        self.sent_count = 0
        self.log_count_label.setText("0 messages")
        self.msg_count_label.setText("Rx: 0 | Tx: 0")
        self.log_signal.emit("INFO", "Log cleared")
    
    def save_config(self):
        save_config(self.config, 'config/client_config.json')
        self.log_signal.emit("SUCCESS", "Configuration saved")
    
    def closeEvent(self, event):
        self.running = False
        if self.comm_interface:
            self.comm_interface.disconnect()
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = ClientGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
