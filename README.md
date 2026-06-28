# IoT远程调试助手 (IoT Remote Debug Assistant)

一款基于 MQTT 协议的物联网远程调试系统，支持跨地域实时远程调试 IoT 设备。

研发人员无需亲临现场，通过公网 MQTT 服务器即可远程查看设备日志、下发调试指令，大幅提升物联网设备部署后的排查效率。

---

## 目录

- [系统架构](#系统架构)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [客户端使用说明](#客户端使用说明)
- [控制台使用说明](#控制台使用说明)
- [TEST 测试命令](#test-测试命令)
- [通信协议](#通信协议)
- [日志类型与颜色](#日志类型与颜色)
- [配置文件](#配置文件)
- [打包为 EXE](#打包为-exe)
- [目录结构](#目录结构)
- [常见问题](#常见问题)

---

## 系统架构

系统由三部分组成：**客户端上位机（Client）** + **公网 MQTT 服务器** + **主机端控制台（Console）**。

```
┌──────────────────────────────────────────────────────────────┐
│                    公网 MQTT 服务器                           │
│                  (您已部署的 MQTT Broker)                     │
│                                                              │
│   Topic A: Elitch/RemotDebug/Client   (Client 发 → Console 收)│
│   Topic B: Elitch/RemotDebug/Console  (Console 发 → Client 收)│
└────────────────────────┬─────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│   客户端上位机       │      │   主机端控制台       │
│   (Client)          │      │   (Console)         │
│                     │      │                     │
│  - 部署在现场PC     │      │  - 部署在研发PC     │
│  - USB/串口连接设备 │      │  - 远程查看设备日志 │
│  - 转发设备日志↑    │      │  - 远程下发调试指令↓│
│  - 转发调试指令↓    │      │  - TEST 测试命令    │
└─────────┬───────────┘      └─────────────────────┘
          │
          ▼
┌─────────────────────┐
│   IoT 设备          │
│  (串口/USB HID)     │
└─────────────────────┘
```

**工作流程：**

1. Client 通过串口/USB HID 连接现场 IoT 设备
2. Client 和 Console 同时连接到同一个公网 MQTT 服务器
3. 设备串口日志 → Client → MQTT → Console（研发人员实时查看）
4. Console 调试指令 → MQTT → Client → 串口 → IoT 设备（远程下发）

---

## 功能特性

### 核心功能

- 远程查看设备日志（带时间戳和类型标识，彩色显示）
- 远程下发调试指令（SHELL 命令，自动追加 `\r\n` 结尾）
- TEST 测试命令（查询 Client 端位置/网络/状态，远程控制 MQTT 连接）
- 串口通信（可配置波特率、数据位、停止位、校验位）
- USB HID 通信
- MQTT 自动重连（断线后自动恢复连接）

### UI 功能

- 专业深色主题（类似 IDE 风格）
- Client 端日志分区显示（MQTT 日志 / 串口日志独立面板）
- 日志过滤搜索框
- 指令历史记录（上下键快速切换，最多 50 条）
- 自动滚动日志（Console 端可开关）
- 状态栏实时显示（连接状态、运行时长、消息收发计数）
- 日志本地保存（File → Save Log）
- 配置持久化（Save Configuration 按钮）

---

## 快速开始

### 方式一：直接使用 EXE（推荐）

无需安装 Python 环境，双击即可运行：

1. 从 `dist/` 目录获取 `IoTDebugClient.exe` 和 `IoTDebugConsole.exe`
2. 将 `IoTDebugClient.exe` 拷贝到现场 PC
3. 将 `IoTDebugConsole.exe` 拷贝到研发人员 PC
4. 双击对应的 exe 文件启动

### 方式二：从源码运行

**环境要求：**
- Python 3.8+
- 已部署的 MQTT 服务器（如 EMQX、Mosquitto 等）

**安装依赖：**

```bash
pip install -r requirements.txt
```

**启动客户端（现场 PC）：**

```bash
python start_client.py
```

**启动控制台（研发人员 PC）：**

```bash
python start_console.py
```

---

## 客户端使用说明

客户端运行在现场 PC，负责连接 IoT 设备并与 MQTT 服务器通信。

### 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│ File  │ Clear │ [Filter logs...]                               │
├─────────────────────────────────────────────────────────────────┤
│  MQTT  │ Device  │                                             │
│ ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│ │ MQTT 配置           │  │  MQTT Log（MQTT通信日志）        │  │
│ │  Broker: [______]   │  │  [14:30:22] [INFO] MQTT已连接   │  │
│ │  Port:   [____]     │  │  [14:30:23] [CMD]  收到SHELL... │  │
│ │  User:   [______]   │  │  [14:30:24] [TEST] location查询 │  │
│ │  Pass:   [******]   │  ├──────────────────────────────────┤  │
│ │  ClientID:[______]  │  │  Serial Log（串口/USB日志）      │  │
│ │  [Connect MQTT]     │  │  [14:30:22] [LOG] 设备启动完成  │  │
│ ├─────────────────────┤  │  [14:30:23] [LOG] WiFi已连接    │  │
│ │ 通信类型: Serial    │  └──────────────────────────────────┘  │
│ │ 端口: [COM3]        │                                        │
│ │ 波特率: [115200]    │                                        │
│ │ [Connect Device]    │                                        │
│ ├─────────────────────┤                                        │
│ │ MQTT: Connected ✓   │                                        │
│ │ Device: Connected ✓ │                                        │
│ └─────────────────────┘                                        │
│ [Save Configuration]                                           │
├─────────────────────────────────────────────────────────────────┤
│ MQTT: Connected | Device: Connected | Up Time: 00:05:32       │
│                                     | Rx: 128 | Tx: 15         │
└─────────────────────────────────────────────────────────────────┘
```

### 操作步骤

**第一步：配置 MQTT 连接**

1. 在 MQTT 标签页输入 MQTT 服务器地址（Broker）
2. 输入端口（默认 1883）
3. 输入用户名和密码
4. Client ID 可留空（自动生成）或自定义（需保证唯一）
5. 点击 **Connect MQTT** 按钮

**第二步：连接 IoT 设备**

1. 切换到 Device 标签页
2. 选择通信类型：**Serial**（串口）或 **USB HID**
3. Serial 模式：选择串口号、波特率、数据位、停止位、校验位
4. USB HID 模式：选择 HID 设备
5. 点击 **Connect Device** 按钮

**第三步：保存配置**

- 点击 **Save Configuration** 保存当前配置，下次启动自动加载

### 数据流向

| 方向 | 说明 |
|------|------|
| 串口 → MQTT | 设备串口数据自动按行解析，封装为 LOG 消息发送到 Console |
| MQTT → 串口 | 收到 Console 的 SHELL 指令，自动追加 `\r\n` 后转发到设备串口 |

---

## 控制台使用说明

控制台运行在研发人员 PC，用于远程查看设备日志和下发调试指令。

### 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│ File  │ Clear │ [Filter logs...] │ Auto Scroll ✓               │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│ │ MQTT 配置           │  │  Remote Device Log（远程日志）    │  │
│ │  Broker: [______]   │  │  [14:30:22] [LOG] 设备启动完成  │  │
│ │  Port:   [____]     │  │  [14:30:23] [LOG] WiFi已连接    │  │
│ │  User:   [______]   │  │  [14:30:24] [TEST] 位置:上海    │  │
│ │  Pass:   [******]   │  │  [14:30:25] [SHELL] 响应:OK     │  │
│ │  ClientID:[______]  │  ├──────────────────────────────────┤  │
│ │  [Connect MQTT]     │  │  CMD: [SHELL ▼]                 │  │
│ ├─────────────────────┤  │  Input: [________________] [Send]│  │
│ │ Target: [client_001]│  └──────────────────────────────────┘  │
│ │ [Connect to Device] │                                        │
│ ├─────────────────────┤                                        │
│ │ MQTT: Connected ✓   │                                        │
│ │ Device: Online      │                                        │
│ └─────────────────────┘                                        │
│ [Save Configuration]                                           │
├─────────────────────────────────────────────────────────────────┤
│ MQTT: Connected | Device: client_001 - Online | Up Time: ...  │
│                                               | Rx: | Tx:      │
└─────────────────────────────────────────────────────────────────┘
```

### 操作步骤

**第一步：配置 MQTT 连接**

1. 输入与客户端相同的 MQTT 服务器信息（Broker、Port、User、Pass、ClientID）
2. 点击 **Connect MQTT** 按钮

**第二步：连接目标设备**

1. 在 Target 输入框中输入目标 Client 的用户名（USERNAME）
2. 点击 **Connect to Device** 按钮
3. 状态显示 Online 表示已建立通信通道

**第三步：查看日志**

- 设备日志会实时显示在 Remote Device Log 区域
- 使用顶部搜索框可过滤日志
- File → Save Log 可导出日志到文件

**第四步：下发指令**

1. 在 CMD 下拉框中选择指令类型：
   - **SHELL** — 向设备串口下发 Shell 命令（自动追加 `\r\n`）
   - **TEST** — 向 Client 端发送测试命令（详见 [TEST 测试命令](#test-测试命令)）
2. 在输入框中输入指令内容
3. 点击 **Send** 或按回车键发送
4. 使用上下方向键切换历史指令

---

## TEST 测试命令

TEST 命令用于 Console 端与 Client 端之间的通讯测试，不涉及设备串口。在 Console 端 CMD 下拉框中选择 **TEST**，在输入框中输入子命令并发送。

### 可用子命令

| 子命令 | 类型 | 说明 |
|--------|------|------|
| `help` | 查询 | 显示所有可用子命令 |
| `location` | 查询 | 查询 Client 端地理位置（国家/城市/ISP/经纬度，基于公网 IP） |
| `netinfo` | 查询 | 查询网络信息（主机名、本地 IP、公网 IP） |
| `auth` | 查询 | 查询 Client 端 MQTT 认证信息（用户名、密码、Broker 地址、ClientID） |
| `status` | 查询 | 查询 Client 端运行状态（MQTT/设备连接状态、运行时长、消息计数） |
| `uptime` | 查询 | 查询 Client 端运行时长 |
| `disconnect_mqtt` | 控制 | 远程断开 Client 端的 MQTT 连接 |
| `reconnect_mqtt` | 控制 | 远程重新连接 Client 端的 MQTT |

### 使用示例

在 Console 端选择 CMD = TEST，依次输入：

```
help              → 查看所有可用命令
location          → 返回: 国家:中国, 城市:上海, ISP:电信...
netinfo           → 返回: 主机名:DESKTOP-XXX, 本地IP:192.168.1.100, 公网IP:...
auth              → 返回: Username:client_001, Password:xxx, Broker:...
status            → 返回: MQTT连接:已连接, 设备连接:已连接, 运行时长:01:23:45
uptime            → 返回: Client运行时长: 01:23:45
disconnect_mqtt   → 返回: MQTT连接正在断开...
reconnect_mqtt    → 返回: MQTT正在重新连接...
```

---

## 通信协议

### Topic 定义

| Topic | 名称 | 发送方 → 接收方 |
|-------|------|-----------------|
| `Elitch/RemotDebug/Client` | Topic A | Client → Console |
| `Elitch/RemotDebug/Console` | Topic B | Console → Client |

- Client 连接后自动订阅 **Topic B**（接收 Console 消息），向 **Topic A** 发送
- Console 连接后自动订阅 **Topic A**（接收 Client 消息），向 **Topic B** 发送

### JSON 消息格式

所有消息统一使用 JSON 格式：

```json
{
  "USERNAME": "client_001",
  "CMD": "LOG",
  "DATA": "设备启动完成",
  "MSG_ID": "a3f2c1d4-e5b6-7890-abcd-ef1234567890",
  "TIMESTAMP": 1719115200000
}
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `USERNAME` | string | 是 | 发送方标识，1~32 字符 |
| `CMD` | string | 是 | 指令名称，仅允许大写字母+下划线 |
| `DATA` | any | 是 | 指令数据，可为对象/字符串/数组，不可为 null |
| `MSG_ID` | string | 是 | 消息唯一 ID，UUID v4 格式 |
| `TIMESTAMP` | number | 是 | 发送时间戳，Unix 毫秒级 |

### CMD 枚举

| CMD | 方向 | 说明 |
|-----|------|------|
| `LOG` | Client → Console | 上报设备日志 |
| `STATUS` | Client → Console | 上报设备状态 |
| `HEARTBEAT` | Client → Console | 心跳保活 |
| `ACK` | 双向 | 消息确认回执 |
| `SHELL` | Console → Client | 下发 Shell 命令到设备串口 |
| `TEST` | 双向 | 测试命令（Console 请求，Client 响应） |

### 消息校验规则

接收方对每条消息进行校验，校验失败时回复 ACK 错误消息：

1. `USERNAME` — 不为空，长度 1~32 字符
2. `CMD` — 不为空，匹配 `^[A-Z_]+$`
3. `DATA` — 字段存在且值不为 null
4. `MSG_ID` — 不为空，UUID v4 格式
5. `TIMESTAMP` — 正整数，与当前时间差不超过 60000ms（防重放）

---

## 日志类型与颜色

| 类型 | 颜色 | 色值 | 说明 |
|------|------|------|------|
| INFO | 灰色 | `#888888` | 普通信息（连接状态等） |
| SUCCESS | 青色 | `#4ec9b0` | 成功操作 |
| ERROR | 红色 | `#f44747` | 错误信息 |
| CMD | 黄色 | `#dcdcaa` | 指令发送/接收 |
| LOG | 蓝色 | `#569cd6` | 设备日志 |
| TEST | 青色 | `#4fc1ff` | TEST 测试命令响应 |

---

## 配置文件

配置文件自动保存在 `config/` 目录下（exe 运行时自动创建）：

| 文件 | 说明 |
|------|------|
| `config/client_config.json` | 客户端配置（MQTT、串口参数等） |
| `config/console_config.json` | 控制台配置（MQTT、目标设备等） |
| `config/cmd_history.json` | 客户端指令历史 |
| `config/console_cmd_history.json` | 控制台指令历史 |

- 指令历史最多保存 50 条
- 日志缓冲区最多保存 5000 行
- 点击 **Save Configuration** 按钮手动保存当前配置

---

## 打包为 EXE

使用 PyInstaller 打包为独立 exe，无需 Python 环境：

```bash
# 打包客户端
pyinstaller --onefile --windowed --name "IoTDebugClient" --paths src --add-data "src;src" start_client.py --noconfirm

# 打包控制台
pyinstaller --onefile --windowed --name "IoTDebugConsole" --paths src --add-data "src;src" start_console.py --noconfirm
```

打包完成后，exe 文件位于 `dist/` 目录：

| 文件 | 大小 | 说明 |
|------|------|------|
| `dist/IoTDebugClient.exe` | ~37 MB | 客户端，拷贝到现场 PC |
| `dist/IoTDebugConsole.exe` | ~37 MB | 控制台，拷贝到研发 PC |

---

## 目录结构

```
.
├── config/                        # 配置文件目录
│   └── config.py                  # 配置数据类与持久化
├── src/
│   ├── client/                    # 客户端模块
│   │   └── client_gui.py          # 客户端 UI 与逻辑
│   ├── comm/                      # 通信接口模块
│   │   └── communication.py       # 串口/USB HID 通信
│   ├── console/                   # 控制台模块
│   │   └── console_gui.py         # 控制台 UI 与逻辑
│   ├── mqtt/                      # MQTT 模块
│   │   └── mqtt_client.py         # MQTT 客户端（含自动重连）
│   ├── protocol/                  # 通信协议模块
│   │   └── protocol.py            # 消息封装/解析/校验
│   └── utils/                     # 工具模块
│       └── logger.py              # 日志工具
├── dist/                          # exe 输出目录
│   ├── IoTDebugClient.exe         # 客户端 exe
│   └── IoTDebugConsole.exe        # 控制台 exe
├── requirements.txt               # Python 依赖列表
├── start_client.py                # 客户端启动脚本
├── start_console.py               # 控制台启动脚本
├── start_client.bat               # 客户端启动批处理
├── start_console.bat              # 控制台启动批处理
├── MQTT_RemoteDebug_Protocol.md   # 通信协议设计文档
└── README.md                      # 本文件
```

---

## 常见问题

### 1. 双击 .py 文件无法启动

使用 `start_client.bat` / `start_console.bat` 启动，或使用 exe 文件。

### 2. MQTT 连接失败

- 检查 Broker 地址和端口是否正确
- 检查用户名和密码是否正确
- 检查 Client ID 是否与服务器上其他客户端冲突
- 检查网络是否能访问 MQTT 服务器
- 系统支持自动重连，网络恢复后会自动重新连接

### 3. Console 端收不到设备日志

- 确认 Client 端和 Console 端连接的是同一个 MQTT 服务器
- 确认 Console 端的 Target 用户名与 Client 端的 USERNAME 一致
- 确认 Client 端设备已连接（Device: Connected）

### 4. 串口数据粘包/显示不正确

- 设备端发送数据建议以 `\n` 结尾，Client 端按行解析
- 若设备无法修改，Client 端会在 200ms 无新数据后自动分割一帧
- 串口读取超时已设为 50ms，保证及时响应

### 5. SHELL 指令下发后设备无响应

- 确认 Client 端设备已连接
- SHELL 指令会自动追加 `\r\n` 结尾，设备端需按行解析
- 检查波特率等串口参数是否与设备一致

### 6. Save Configuration 闪退

已修复。配置保存时会自动创建 `config/` 目录，exe 运行时不再崩溃。

### 7. USB HID 无法使用

需安装 hid 库的系统依赖：
- Windows：通常无需额外操作
- Linux：`sudo apt install libhidapi-hidraw0`
- macOS：`brew install hidapi`
brew install hidapi`
