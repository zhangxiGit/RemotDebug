# MQTT 远程调试通信协议实现需求

## 一、Topic 定义

| Topic | 名称 |
|---|---|
| **Topic A** | `Elitch/RemotDebug/Client` |
| **Topic B** | `Elitch/RemotDebug/Console` |

## 二、通信规则

| 端 | 连接后自动订阅 | 发送消息目标 |
|---|---|---|
| **Client 端** | Topic B（接收 Console 消息） | Topic A |
| **Console 端** | Topic A（接收 Client 消息） | Topic B |

## 三、JSON 消息格式

所有消息统一使用 JSON 格式。

```json
{
  "USERNAME": "client_001",
  "CMD": "LOG",
  "DATA": {
    "level": "info",
    "message": "设备启动完成",
    "timestamp": 1719115200000
  },
  "MSG_ID": "a3f2c1d4-e5b6-7890-abcd-ef1234567890",
  "TIMESTAMP": 1719115200000,
  "VERSION": "1.0"
}
```

## 四、字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `USERNAME` | string | 是 | 发送方标识，非空，长度 1~32 |
| `CMD` | string | 是 | 指令名称，仅允许大写字母+下划线 |
| `DATA` | any | 是 | 指令数据，可为对象/字符串/数组，不可为 null |
| `MSG_ID` | string | 是 | 消息唯一 ID，UUID v4 格式，用于去重与追踪 |
| `TIMESTAMP` | number | 是 | 发送时间戳，Unix 毫秒级 |
| `VERSION` | string | 否 | 协议版本号，默认 `"1.0"` |

## 五、CMD 枚举

| CMD | 方向 | 说明 |
|---|---|---|
| `LOG` | Client → Console | 上报日志 |
| `STATUS` | Client → Console | 上报设备状态 |
| `HEARTBEAT` | Client → Console | 心跳保活 |
| `ACK` | 双向 | 消息确认回执 |
| `EXEC` | Console → Client | 下发执行指令 |
| `CONFIG` | Console → Client | 下发配置参数 |

## 六、消息校验规则

发送前/接收后须做如下校验：

1. `USERNAME` — 不为空，长度 1~32 字符
2. `CMD` — 不为空，匹配正则 `^[A-Z_]+$`
3. `DATA` — 字段存在且值不为 null / undefined
4. `MSG_ID` — 不为空，建议校验 UUID v4 格式
5. `TIMESTAMP` — 须为正整数，与接收方当前时间差不超过 60000ms（防重放，可配置）
6. `VERSION` — 若存在，匹配正则 `^\d+\.\d+$`

任意校验不通过，接收方须回复错误消息。

## 七、错误响应格式

当消息校验失败时，接收方回复：

```json
{
  "USERNAME": "console_001",
  "CMD": "ACK",
  "DATA": {
    "code": 400,
    "msg": "USERNAME 字段缺失",
    "ref_msg_id": "a3f2c1d4-e5b6-7890-abcd-ef1234567890"
  },
  "MSG_ID": "a1b2c3d4-e5f6-7890-abcd-ef0987654321",
  "TIMESTAMP": 1719115200001,
  "VERSION": "1.0"
}
```

## 八、实现要求


1. 连接后自动订阅对应 Topic，断连后自动重连
2. 把连接MQTT服务器的`USERNAME`，所有发出的消息填入该值
3. 每次发送消息自动生成 `MSG_ID`（UUID）和 `TIMESTAMP`
4. 收到消息后先做校验，校验不通过按第七节格式回复错误
5. 收到的合法消息按 `[USERNAME] [CMD] [DATA]` 格式打印到控制台
6. Client删除输入功能，所有命令听过USB/串口通讯日志获取后，回传到Console。
7. Console端输入功能，新增[CMD]选择功能，输入内容均为DATA。

