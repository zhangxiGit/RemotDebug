# MQTT远程调试通信协议实现规范

## Why
当前系统使用简单的Topic结构和裸文本消息通信，无法满足协议规范要求。需要按照 `MQTT_RemoteDebug_Protocol.md` 实现统一的JSON消息格式、固定Topic、消息校验和CMD枚举，以提升通信的可靠性、可追溯性和可扩展性。

## What Changes
- **BREAKING** Topic结构从 `iot_debug/{device_id}/log|cmd|status` 改为固定双Topic：
  - Topic A: `Elitch/RemotDebug/Client`（Client发送目标，Console订阅）
  - Topic B: `Elitch/RemotDebug/Console`（Console发送目标，Client订阅）
- **BREAKING** 消息格式从裸文本改为统一JSON格式（含USERNAME/CMD/DATA/MSG_ID/TIMESTAMP/VERSION）
- 新增协议模块 `src/protocol/protocol.py`，负责消息封装、解析、校验
- MQTT客户端新增自动重连功能
- Client端删除指令输入框，日志通过USB/串口获取后以JSON格式回传Console
- Console端输入框新增CMD下拉选择（EXEC/CONFIG），输入内容作为DATA字段
- 合法消息按 `[USERNAME] [CMD] [DATA]` 格式打印到日志区
- 校验失败时自动回复ACK错误消息

## Impact
- 受影响的模块：协议模块(新增)、MQTT客户端、客户端UI、控制台UI
- 受影响的文件：
  - `src/protocol/protocol.py` (新增)
  - `src/mqtt/mqtt_client.py`
  - `src/client/client_gui.py`
  - `src/console/console_gui.py`

## ADDED Requirements

### Requirement: 协议消息封装与解析
系统 SHALL 提供统一的JSON消息封装和解析能力。

#### Scenario: 封装消息
- **WHEN** 端需要发送消息
- **THEN** 系统自动生成MSG_ID(UUID v4)和TIMESTAMP(毫秒)，填入USERNAME，组装为JSON：
  ```json
  {"USERNAME":"...", "CMD":"...", "DATA":..., "MSG_ID":"...", "TIMESTAMP":..., "VERSION":"1.0"}
  ```

#### Scenario: 解析消息
- **WHEN** 接收到MQTT消息
- **THEN** 系统解析JSON并校验所有必填字段

### Requirement: 消息校验
系统 SHALL 对收到的消息进行校验，校验规则：
1. USERNAME — 不为空，长度1~32字符
2. CMD — 不为空，匹配正则 `^[A-Z_]+$`
3. DATA — 字段存在且值不为null
4. MSG_ID — 不为空，UUID v4格式
5. TIMESTAMP — 正整数，与当前时间差不超过60000ms
6. VERSION — 若存在，匹配正则 `^\d+\.\d+$`

#### Scenario: 校验通过
- **WHEN** 收到的消息所有字段校验通过
- **THEN** 按 `[USERNAME] [CMD] [DATA]` 格式打印到日志区

#### Scenario: 校验失败
- **WHEN** 收到的消息任一字段校验不通过
- **THEN** 回复ACK错误消息，包含code=400、msg错误描述、ref_msg_id引用原消息ID

### Requirement: CMD枚举
系统 SHALL 支持以下CMD指令：
| CMD | 方向 | 说明 |
|---|---|---|
| LOG | Client → Console | 上报日志 |
| STATUS | Client → Console | 上报设备状态 |
| HEARTBEAT | Client → Console | 心跳保活 |
| ACK | 双向 | 消息确认回执 |
| EXEC | Console → Client | 下发执行指令 |
| CONFIG | Console → Client | 下发配置参数 |

### Requirement: 自动重连
系统 SHALL 在MQTT断连后自动重连。

#### Scenario: 断线重连
- **WHEN** MQTT连接断开
- **THEN** 系统自动尝试重连，重连后自动重新订阅对应Topic

## MODIFIED Requirements

### Requirement: Topic结构
系统 SHALL 使用固定双Topic通信：
- Client端连接后自动订阅Topic B（`Elitch/RemotDebug/Console`），发送消息到Topic A（`Elitch/RemotDebug/Client`）
- Console端连接后自动订阅Topic A（`Elitch/RemotDebug/Client`），发送消息到Topic B（`Elitch/RemotDebug/Console`）

**变更内容：**
- 移除基于device_id的动态Topic
- 连接MQTT后自动订阅对应Topic

### Requirement: USERNAME来源
系统 SHALL 使用MQTT连接配置的username作为所有发出消息的USERNAME字段值。

**变更内容：**
- 不再使用device_id作为发送方标识
- USERNAME直接取自MQTT配置的username字段

### Requirement: Client端UI
系统 SHALL 移除Client端的指令输入框，Client端仅作为日志转发器。

**变更内容：**
- 删除指令输入框和发送按钮
- 删除指令历史记录功能
- USB/串口接收的数据以LOG类型JSON消息发送到Console
- 收到Console的EXEC/CONFIG指令后转发到USB/串口设备

### Requirement: Console端UI
系统 SHALL 在Console端输入区域新增CMD下拉选择框。

**变更内容：**
- 新增CMD下拉框，选项：EXEC、CONFIG
- 输入框内容作为DATA字段值
- 发送时自动封装为JSON消息（含USERNAME/CMD/DATA/MSG_ID/TIMESTAMP/VERSION）

## REMOVED Requirements
无
