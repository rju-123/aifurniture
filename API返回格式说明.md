# 百度物体检测API返回格式说明

## 当前问题

系统提示"无法自动识别房间尺寸"，这是因为：

**百度物体检测API (`/rest/2.0/image-classify/v1/object_detect`) 只返回检测到的物体信息，不返回房间尺寸。**

## 需要的信息

为了能够自动识别房间尺寸，我需要您提供以下信息之一：

### 方案1：如果您的API确实返回了尺寸信息

请提供API实际返回的JSON格式示例，例如：

```json
{
  "result": [
    {
      "name": "沙发",
      "score": 0.95,
      "location": {...}
    }
  ],
  "room_length": 5.0,  // 如果API返回了这些字段
  "room_width": 4.0
}
```

或者可能是其他格式，请提供实际的返回数据。

### 方案2：如果API不返回尺寸，但您有其他API

如果您有专门用于识别房间尺寸的API端点，请提供：
- API端点地址
- 返回的JSON格式示例

### 方案3：使用EasyDL自定义模型

如果您在百度EasyDL平台训练了房间尺寸识别模型，请提供：
- API端点地址（格式通常是：`https://aip.baidubce.com/rpc/2.0/ai_custom/v1/...`）
- 返回的JSON格式示例

## 如何获取API返回数据

1. **查看日志文件**：
   - 文件位置：`project_log/project.log`
   - 搜索 "百度物体检测API返回结果"
   - 复制完整的JSON数据

2. **使用浏览器开发者工具**：
   - 打开开发者工具（F12）
   - 切换到 Network（网络）标签
   - 上传图片后，找到对百度API的请求
   - 查看 Response（响应）内容

3. **直接告诉我**：
   - 如果API返回了尺寸相关的字段，请告诉我字段名称
   - 例如：`length`、`width`、`room_length`、`room_width` 等

## 当前代码的解析逻辑

代码会尝试从以下位置解析尺寸：

1. 直接字段：`result.length`、`result.width`
2. data字段：`result.data.length`、`result.data.width`
3. result字段：`result.result.length`、`result.result.width`
4. 其他字段名：`room_length`、`room_width`、`long`、`wide`、`长`、`宽`

如果您的API返回格式不同，请告诉我，我可以调整解析逻辑。

## 临时解决方案

目前系统已经实现了手动输入功能，用户可以：
1. 上传图片
2. 当API无法识别时，手动输入房间尺寸
3. 继续后续流程

这个功能已经可以正常使用。
