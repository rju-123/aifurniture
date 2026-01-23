# API调用失败解决方案

## 错误分析

**错误信息**: `Unsupported openapi method (错误码: 3)`

**原因**: 
- 百度智能云图像识别服务**没有提供直接的房间尺寸识别API**
- 代码中使用的 `/rest/2.0/image-classify/v1/room_layout` 端点不存在

## 解决方案

### 方案1：使用EasyDL自定义模型（推荐）

如果您已经在百度EasyDL平台训练了房间尺寸识别模型：

1. **在 `.env` 文件中添加自定义API端点**：
```env
BAIDU_API_KEY=您的API_KEY
BAIDU_SECRET_KEY=您的SECRET_KEY
BAIDU_ROOM_SIZE_API_ENDPOINT=https://aip.baidubce.com/rpc/2.0/ai_custom/v1/您的模型路径
```

2. **获取EasyDL API端点**：
   - 登录 [百度EasyDL控制台](https://ai.baidu.com/easydl/)
   - 进入您的模型页面
   - 复制API调用地址
   - 格式通常为：`https://aip.baidubce.com/rpc/2.0/ai_custom/v1/...`

3. **重新启动应用**

### 方案2：暂时禁用自动识别，使用手动输入（当前可用）

如果您还没有训练EasyDL模型，可以：

1. **修改代码，跳过API调用**（已实现自动降级）
2. **用户手动输入尺寸**（界面已支持）

当前代码已经实现了自动降级机制：
- 如果API调用失败，会自动提示用户手动输入尺寸
- 不会影响后续流程

### 方案3：使用其他百度API组合（需要开发）

可以使用以下API组合，但需要额外开发：

1. **场景识别API** - 识别是否为客厅
2. **物体检测API** - 检测参考物（门、窗户、已知尺寸的家具等）
3. **图像处理算法** - 根据参考物计算房间尺寸

**API端点示例**：
```python
# 场景识别
https://aip.baidubce.com/rest/2.0/image-classify/v2/advanced_general

# 物体检测
https://aip.baidubce.com/rest/2.0/image-classify/v1/object_detect
```

### 方案4：使用第三方API服务

可以考虑使用其他服务商的房间尺寸识别API，例如：
- 腾讯云
- 阿里云
- 其他专业的空间识别服务

## 当前代码修改说明

我已经修改了代码，使其支持：

1. **自定义API端点配置**：可以通过环境变量配置EasyDL模型端点
2. **更好的错误处理**：API调用失败时，自动提示用户手动输入
3. **日志记录**：记录完整的API响应，便于调试

## 推荐做法

**短期方案**（立即可用）：
- 使用手动输入功能
- 界面已经实现，用户可以输入准确的尺寸

**长期方案**（推荐）：
1. 在百度EasyDL平台训练房间尺寸识别模型
2. 或者使用其他深度学习模型进行识别
3. 配置自定义API端点

## 验证步骤

1. **检查环境变量**：
   ```bash
   # 确认 .env 文件中是否有配置
   cat .env | grep BAIDU
   ```

2. **查看日志**：
   - 检查 `project_log/project.log` 文件
   - 查看完整的API返回结果

3. **测试手动输入**：
   - 上传图片
   - 当API调用失败时，使用手动输入功能
   - 验证后续流程是否正常

## 相关文档

- [百度EasyDL文档](https://ai.baidu.com/ai-doc/EASYDL)
- [百度图像识别API文档](https://cloud.baidu.com/doc/IMAGERECOGNITION/index.html)
- [项目配置说明](./百度智能云API配置说明.md)

## 需要帮助？

如果您：
1. 已经在EasyDL训练了模型，请提供API端点，我可以帮您配置
2. 想要实现其他API组合方案，我可以协助开发
3. 需要更多调试信息，请查看日志文件并告诉我具体的错误信息
