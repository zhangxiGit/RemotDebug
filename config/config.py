import os
from dataclasses import dataclass, field

@dataclass
class MQTTConfig:
    broker: str = "mqtt.example.com"
    port: int = 1883
    username: str = ""
    password: str = ""
    client_id: str = ""
    keepalive: int = 60
    client_id_prefix: str = "iot_debug_"

@dataclass
class SerialConfig:
    port: str = "COM3"
    baud_rate: int = 115200
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    timeout: float = 1.0

@dataclass
class HIDConfig:
    vendor_id: int = 0x0000
    product_id: int = 0x0000
    usage_page: int = 0xFF00
    usage: int = 0x0001

@dataclass
class LogConfig:
    log_level: str = "INFO"
    log_file: str = "debug.log"
    max_file_size: int = 1024 * 1024 * 10
    backup_count: int = 5

@dataclass
class AppConfig:
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)
    hid: HIDConfig = field(default_factory=HIDConfig)
    log: LogConfig = field(default_factory=LogConfig)

def load_config(file_path: str = None) -> AppConfig:
    config = AppConfig()
    if file_path and os.path.exists(file_path):
        try:
            import json
            with open(file_path, 'r') as f:
                data = json.load(f)
                if 'mqtt' in data:
                    config.mqtt = MQTTConfig(**data['mqtt'])
                if 'serial' in data:
                    config.serial = SerialConfig(**data['serial'])
                if 'hid' in data:
                    config.hid = HIDConfig(**data['hid'])
                if 'log' in data:
                    config.log = LogConfig(**data['log'])
        except Exception as e:
            print(f"Failed to load config file: {e}")
    return config

def save_config(config: AppConfig, file_path: str):
    import json
    import os
    # 确保目录存在，避免exe运行时因目录缺失而崩溃
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    data = {
        'mqtt': {
            'broker': config.mqtt.broker,
            'port': config.mqtt.port,
            'username': config.mqtt.username,
            'password': config.mqtt.password,
            'client_id': config.mqtt.client_id,
            'keepalive': config.mqtt.keepalive,
            'client_id_prefix': config.mqtt.client_id_prefix
        },
        'serial': {
            'port': config.serial.port,
            'baud_rate': config.serial.baud_rate,
            'data_bits': config.serial.data_bits,
            'parity': config.serial.parity,
            'stop_bits': config.serial.stop_bits,
            'timeout': config.serial.timeout
        },
        'hid': {
            'vendor_id': config.hid.vendor_id,
            'product_id': config.hid.product_id,
            'usage_page': config.hid.usage_page,
            'usage': config.hid.usage
        },
        'log': {
            'log_level': config.log.log_level,
            'log_file': config.log.log_file,
            'max_file_size': config.log.max_file_size,
            'backup_count': config.log.backup_count
        }
    }
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
