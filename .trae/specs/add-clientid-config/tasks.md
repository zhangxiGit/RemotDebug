# Tasks

- [x] Task 1: 更新配置模块，添加client_id字段
  - [x] SubTask 1.1: 在MQTTConfig中添加client_id字段
  - [x] SubTask 1.2: 更新save_config函数保存client_id

- [x] Task 2: 更新MQTT客户端，支持自定义Client ID
  - [x] SubTask 2.1: 修改_generate_client_id方法，优先使用配置的client_id

- [x] Task 3: 更新客户端UI，添加Client ID输入框
  - [x] SubTask 3.1: 在MQTT配置区域添加Client ID输入框
  - [x] SubTask 3.2: 在connect_mqtt方法中保存client_id到配置

- [x] Task 4: 更新控制台UI，添加Client ID输入框
  - [x] SubTask 4.1: 在MQTT配置区域添加Client ID输入框
  - [x] SubTask 4.2: 在connect_mqtt方法中保存client_id到配置

# Task Dependencies
无
