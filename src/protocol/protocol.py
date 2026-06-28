"""MQTT 远程调试通信协议模块。

负责消息的封装、解析与校验，定义 Topic 与 CMD 常量。
"""

import json
import uuid
import time
import re
from typing import Any, Optional, Tuple

# ==================== Topic 常量定义 ====================
# Client 发送目标，Console 订阅
TOPIC_A = "Elitch/RemotDebug/Client"
# Console 发送目标，Client 订阅
TOPIC_B = "Elitch/RemotDebug/Console"

# ==================== CMD 枚举常量 ====================
# Client → Console，上报日志
CMD_LOG = "LOG"
# Client → Console，上报设备状态
CMD_STATUS = "STATUS"
# Client → Console，心跳保活
CMD_HEARTBEAT = "HEARTBEAT"
# 双向，消息确认回执
CMD_ACK = "ACK"
# Console → Client，下发执行指令
CMD_EXEC = "EXEC"
# Console → Client，下发配置参数
CMD_CONFIG = "CONFIG"
# Console → Client，下发Shell命令
CMD_SHELL = "SHELL"
# 双向，测试命令（Console → Client 请求，Client → Console 响应）
CMD_TEST = "TEST"

# ==================== 协议默认值 ====================
# 协议默认版本号
DEFAULT_VERSION = "1.0"
# 时间戳允许的最大偏差（毫秒），用于防重放
_MAX_TIMESTAMP_DIFF_MS = 60000

# ==================== 校验正则 ====================
# CMD 仅允许大写字母与下划线
_CMD_PATTERN = re.compile(r"^[A-Z_]+$")
# VERSION 形如 1.0
_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
# UUID v4 格式（忽略大小写）
_UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def build_message(username: str, cmd: str, data: Any) -> str:
    """封装消息为 JSON 字符串。

    自动生成 MSG_ID（UUID v4）和 TIMESTAMP（Unix 毫秒级时间戳），
    VERSION 默认 "1.0"。

    :param username: 发送方标识
    :param cmd: 指令名称
    :param data: 指令数据，可为对象/字符串/数组
    :return: JSON 格式的消息字符串
    """
    message = {
        "USERNAME": username,
        "CMD": cmd,
        "DATA": data,
        "MSG_ID": str(uuid.uuid4()),
        "TIMESTAMP": int(time.time() * 1000),
    }
    return json.dumps(message, ensure_ascii=False, separators=(',', ':'))


def parse_message(payload) -> Optional[dict]:
    """解析消息。

    :param payload: bytes 或 str 类型的消息内容
    :return: 解析后的字典；解析失败返回 None
    """
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        return json.loads(payload)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def validate_message(msg: dict) -> Tuple[bool, Optional[str]]:
    """校验消息字段。

    校验规则：
      a. USERNAME — 不为空，长度 1~32 字符
      b. CMD — 不为空，匹配正则 ^[A-Z_]+$
      c. DATA — 字段存在且值不为 None
      d. MSG_ID — 不为空，校验 UUID v4 格式
      e. TIMESTAMP — 须为正整数，与当前时间差不超过 60000ms
      f. VERSION — 若存在，匹配正则 ^\\d+\\.\\d+$

    :param msg: 待校验的消息字典
    :return: (True, None) 表示校验通过；(False, "错误描述") 表示校验失败
    """
    if not isinstance(msg, dict):
        return False, "消息不是有效的字典对象"

    # a. USERNAME — 不为空，长度 1~32 字符
    username = msg.get("USERNAME")
    if not isinstance(username, str) or not username:
        return False, "USERNAME 字段缺失或为空"
    if not (1 <= len(username) <= 32):
        return False, "USERNAME 长度须在 1~32 字符之间"

    # b. CMD — 不为空，匹配正则 ^[A-Z_]+$
    cmd = msg.get("CMD")
    if not isinstance(cmd, str) or not cmd:
        return False, "CMD 字段缺失或为空"
    if not _CMD_PATTERN.match(cmd):
        return False, "CMD 格式不合法，仅允许大写字母与下划线"

    # c. DATA — 字段存在且值不为 None
    if "DATA" not in msg:
        return False, "DATA 字段缺失"
    if msg.get("DATA") is None:
        return False, "DATA 字段值不能为 None"

    # d. MSG_ID — 不为空，校验 UUID v4 格式
    msg_id = msg.get("MSG_ID")
    if not isinstance(msg_id, str) or not msg_id:
        return False, "MSG_ID 字段缺失或为空"
    if not _UUID_V4_PATTERN.match(msg_id):
        return False, "MSG_ID 不是合法的 UUID v4 格式"

    # e. TIMESTAMP — 须为正整数，与当前时间差不超过 60000ms
    timestamp = msg.get("TIMESTAMP")
    # bool 是 int 的子类，需排除
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        return False, "TIMESTAMP 须为整数"
    if timestamp <= 0:
        return False, "TIMESTAMP 须为正整数"
    current_ms = int(time.time() * 1000)
    if abs(current_ms - timestamp) > _MAX_TIMESTAMP_DIFF_MS:
        return False, "TIMESTAMP 与当前时间差超过 60000ms"

    # f. VERSION — 若存在，匹配正则 ^\d+\.\d+$
    if "VERSION" in msg:
        version = msg.get("VERSION")
        if not isinstance(version, str) or not _VERSION_PATTERN.match(version):
            return False, "VERSION 格式不合法，须匹配 ^\\d+\\.\\d+$"

    return True, None


def build_error_response(username: str, ref_msg_id: str, error_msg: str) -> str:
    """构建错误响应消息。

    CMD 为 "ACK"，DATA 包含 code=400、msg=error_msg、ref_msg_id=ref_msg_id。
    自动生成 MSG_ID 和 TIMESTAMP。

    :param username: 发送方标识
    :param ref_msg_id: 引用的原消息 ID
    :param error_msg: 错误描述
    :return: JSON 格式的错误响应字符串
    """
    data = {
        "code": 400,
        "msg": error_msg,
        "ref_msg_id": ref_msg_id,
    }
    return build_message(username, CMD_ACK, data)


def build_ack_response(username: str, ref_msg_id: str) -> str:
    """构建成功 ACK 响应消息。

    CMD 为 "ACK"，DATA 包含 code=200、msg="OK"、ref_msg_id=ref_msg_id。
    自动生成 MSG_ID 和 TIMESTAMP。

    :param username: 发送方标识
    :param ref_msg_id: 引用的原消息 ID
    :return: JSON 格式的成功响应字符串
    """
    data = {
        "code": 200,
        "msg": "OK",
        "ref_msg_id": ref_msg_id,
    }
    return build_message(username, CMD_ACK, data)
