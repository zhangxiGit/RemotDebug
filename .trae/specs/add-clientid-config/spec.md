# IoT远程调试助手 - MQTT Client ID配置功能规范

## Why
当前MQTT配置界面缺少Client ID配置字段，导致用户无法指定自定义的Client ID。某些MQTT服务器（如OneNET、阿里云IoT等）要求特定的Client ID格式进行设备鉴权，自动生成Client ID可能导致连接失败或鉴权问题。

## What Changes
- 在MQTTConfig配置类中添加`client_id`字段
- 在客户端和控制台的MQTT配置UI中添加Client ID输入框
- 修改MQTT客户端逻辑，支持使用自定义Client ID或自动生成
- 配置持久化时保存Client ID设置

## Impact
- 受影响的模块：配置模块、MQTT客户端、客户端UI、控制台UI
- 受影响的文件：
  - `config/config.py`
  - `src/mqtt/mqtt_client.py`
  - `src/client/client_gui.py`
  - `src/console/console_gui.py`

## ADDED Requirements

### Requirement: MQTT Client ID配置
系统 SHALL 提供MQTT Client ID的自定义配置能力，允许用户指定或自动生成Client ID。

#### Scenario: 用户自定义Client ID
- **WHEN** 用户在Client ID输入框中输入自定义值
- **THEN** 系统使用该自定义Client ID连接MQTT服务器

#### Scenario: 自动生成Client ID
- **WHEN** 用户留空Client ID输入框
- **THEN** 系统自动生成格式为 `iot_debug_xxxxxxx` 的Client ID（xxxxxxx为8位随机字符串）

#### Scenario: 配置持久化
- **WHEN** 用户保存配置
- **THEN** 自定义Client ID设置被保存到配置文件

## MODIFIED Requirements

### Requirement: MQTT连接
系统 SHALL 在连接MQTT时使用配置的Client ID（如有）或自动生成的Client ID。

**变更内容：**
- MQTT客户端初始化时检查`config.client_id`
- 如果配置了非空Client ID，则使用配置值
- 如果配置为空，则调用`_generate_client_id()`生成

### Requirement: MQTT配置UI
系统 SHALL 在MQTT配置区域提供以下输入字段：
- Broker（服务器地址）
- Port（端口号）
- User（用户名）
- Pass（密码）
- **Client ID（客户端标识）** - 新增字段

**变更内容：**
- Client ID输入框支持留空
- 输入框显示占位符提示文本"Leave empty for auto-generate"

## REMOVED Requirements
无
