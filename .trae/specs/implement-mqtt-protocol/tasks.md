# Tasks

- [x] Task 1: 创建协议模块 `src/protocol/protocol.py`
  - [x] SubTask 1.1: 实现消息封装函数 `build_message(username, cmd, data)`，自动生成MSG_ID和TIMESTAMP
  - [x] SubTask 1.2: 实现消息解析函数 `parse_message(payload)`，返回解析后的字典或错误
  - [x] SubTask 1.3: 实现消息校验函数 `validate_message(msg)`，校验所有字段规则
  - [x] SubTask 1.4: 实现错误响应构建函数 `build_error_response(username, ref_msg_id, error_msg)`
  - [x] SubTask 1.5: 定义CMD枚举常量和Topic常量

- [x] Task 2: 更新MQTT客户端 `src/mqtt/mqtt_client.py`
  - [x] SubTask 2.1: 添加自动重连功能（使用reconnect_delay_set和on_disconnect重连）
  - [x] SubTask 2.2: 连接成功后通过回调通知，由UI层决定订阅哪个Topic

- [x] Task 3: 更新Client端 `src/client/client_gui.py`
  - [x] SubTask 3.1: 修改Topic为固定Topic A/B，连接后自动订阅Topic B
  - [x] SubTask 3.2: USERNAME使用MQTT配置的username
  - [x] SubTask 3.3: 删除指令输入框、发送按钮、指令历史相关代码
  - [x] SubTask 3.4: USB/串口接收数据后封装为LOG类型JSON消息发送到Topic A
  - [x] SubTask 3.5: 收到Topic B消息后解析校验，EXEC/CONFIG指令转发到USB/串口
  - [x] SubTask 3.6: 校验失败时回复ACK错误消息到Topic A
  - [x] SubTask 3.7: 合法消息按 `[USERNAME] [CMD] [DATA]` 格式打印

- [x] Task 4: 更新Console端 `src/console/console_gui.py`
  - [x] SubTask 4.1: 修改Topic为固定Topic A/B，连接后自动订阅Topic A
  - [x] SubTask 4.2: USERNAME使用MQTT配置的username
  - [x] SubTask 4.3: 新增CMD下拉选择框（EXEC、CONFIG）
  - [x] SubTask 4.4: 输入内容作为DATA，封装JSON消息发送到Topic B
  - [x] SubTask 4.5: 收到Topic A消息后解析校验，按 `[USERNAME] [CMD] [DATA]` 打印
  - [x] SubTask 4.6: 校验失败时回复ACK错误消息到Topic B
  - [x] SubTask 4.7: 移除device_id相关逻辑（Device Selection区域改为显示USERNAME）

# Task Dependencies
- Task 3 depends on Task 1
- Task 4 depends on Task 1
- Task 2 无依赖，可与Task 1并行
