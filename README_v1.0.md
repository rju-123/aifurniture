# AI智能家装系统 v1.0

## 🎯 项目概述

AI智能家装系统v1.0是一个基于千问图像编辑模型的智能家装设计工具。用户可以上传客厅图片，选择家具，通过画笔涂画的方式标记家具放置位置，系统将自动生成真实的装修效果图。

## 🚀 v1.0 新特性

### 核心功能重构
1. **单家具选择模式** - 简化用户操作，每次只能选择一个家具
2. **画笔涂画功能** - 用户通过画笔在客厅图片上涂画浅蓝色区域标记家具位置
3. **Mask图片生成** - 自动保存用户绘制的mask图片用于AI处理
4. **千问图像融合** - 集成DashScope MultiModalConversation API
5. **实时预览** - 支持涂画撤销、清除等操作

### 技术架构
- **后端**: Flask + DashScope API
- **前端**: HTML5 Canvas + JavaScript
- **AI模型**: qwen-image-edit-plus
- **图像处理**: PIL + Base64编码

## 📁 项目结构

```
AI_DECORATION/
├── src/
│   ├── app.py                 # Flask主应用 (v1.0重构)
│   └── templates/
│       └── index_v1.html      # v1.0前端界面
├── data/
│   ├── user/                  # 用户上传的客厅图片
│   ├── furniture/             # 家具库图片
│   ├── masks/                 # 用户绘制的mask图片 (新增)
│   └── output/                # 生成的装修效果图
├── test/
│   ├── test_qwen_image_fusion.py      # 图像融合测试
│   └── test_qwen_image_fusion2.py     # v1.0参考实现
├── project_log/               # 项目日志
└── requirements.txt           # 依赖包列表
```

## 🛠️ 安装与配置

### 1. 环境要求
- Python 3.8+
- 推荐使用conda环境

### 2. 创建环境
```bash
conda create -n ai_decoration python=3.9
conda activate ai_decoration
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
pip install dashscope>=1.23.8
```

### 4. 环境变量配置
创建 `.env` 文件：
```bash
DASHSCOPE_API_KEY=your-dashscope-api-key
```

### 5. 启动应用
```bash
cd src
python app.py
```

访问 `http://localhost:5000` 使用v1.0界面

## 🎨 使用流程

### 步骤1: 上传客厅图片
- 点击或拖拽上传客厅图片
- 支持JPG、PNG、GIF格式
- 最大文件大小16MB

### 步骤2: 选择家具
- 从家具库中选择一个家具
- v1.0版本限制为单选模式

### 步骤3: 涂画放置区域
- 使用画笔在客厅图片上涂画浅蓝色区域
- 可调节画笔大小(5-50px)
- 支持撤销和清除操作
- 蓝色区域表示家具的放置位置

### 步骤4: 生成效果图
- 点击"生成装修效果图"按钮
- 系统自动调用千问AI进行图像融合
- 生成真实的装修效果图

## 🔧 API接口

### 核心接口

#### 1. 上传客厅图片
```
POST /upload
Content-Type: multipart/form-data

Response:
{
  "success": true,
  "filename": "uuid_image.jpg",
  "message": "客厅图片上传成功"
}
```

#### 2. 获取家具列表
```
GET /furniture

Response:
{
  "furniture": [
    {
      "name": "sofa_1.jpg",
      "path": "/furniture/sofa_1.jpg",
      "display_name": "sofa_1"
    }
  ]
}
```

#### 3. 保存Mask图片
```
POST /save_mask
Content-Type: application/json

Body:
{
  "original_image": "uuid_image.jpg",
  "mask_data": "data:image/png;base64,..."
}

Response:
{
  "success": true,
  "mask_filename": "image_mask_20240101_120000.png",
  "mask_path": "/masks/image_mask_20240101_120000.png"
}
```

#### 4. 生成装修效果图
```
POST /generate_v1
Content-Type: application/json

Body:
{
  "original_image": "uuid_image.jpg",
  "selected_furniture": "sofa_1.jpg",
  "mask_filename": "image_mask_20240101_120000.png"
}

Response:
{
  "success": true,
  "generated_images": [
    {
      "filename": "generated_v1_20240101_120000_1.jpg",
      "path": "/output/generated_v1_20240101_120000_1.jpg",
      "url": "https://..."
    }
  ],
  "message": "成功生成 1 张装修效果图"
}
```

## 🧪 测试

### 运行图像融合测试
```bash
cd test
python test_qwen_image_fusion2.py
```

### 测试文件说明
- `test_qwen_image_fusion2.py` - v1.0参考实现，包含完整的API调用逻辑
- 测试需要准备 `keting_mask2.png` 和 `sofa1.png` 图片

## 📝 配置说明

### Prompt配置
系统使用的AI提示词位于 `src/app.py` 的 `generate_decoration_v1()` 函数中：

```python
prompt_text = """在图一客厅中我涂成蓝色的部分放置图二中选择的沙发，要求自然的融入到图一中，
尤其注意:客厅图一我没有涂蓝色的部分不要做任何变动。
保持沙发的原始外观特征，调整光影和透视以匹配客厅环境。
生成的图片中我用于标记沙发放置位置的蓝色不要再出现"""
```

### 模型配置
- **模型**: qwen-image-edit-plus
- **API**: DashScope MultiModalConversation
- **参数**: 
  - n=1 (生成1张图片)
  - watermark=False
  - seed=12345 (固定随机种子)

## 🔍 日志系统

### 项目日志
- 位置: `project_log/project.log`
- 记录: 用户操作、API调用、错误信息

### 生成日志
- 位置: `project_log/generation_v1_*.json`
- 内容: 完整的生成请求和响应数据

## 🚨 故障排除

### 常见问题

1. **DashScope库未安装**
   ```bash
   pip install dashscope>=1.23.8
   ```

2. **API Key未配置**
   - 检查 `.env` 文件中的 `DASHSCOPE_API_KEY`
   - 或在代码中直接设置API Key

3. **图片上传失败**
   - 检查文件格式和大小限制
   - 确保 `data/user` 目录存在且可写

4. **Canvas画布问题**
   - 确保浏览器支持HTML5 Canvas
   - 检查JavaScript控制台错误

### 调试模式
启动应用时会显示详细的系统信息：
```
✅ DashScope库可用，图像生成功能正常
家具文件夹路径: /path/to/furniture
🚀 启动AI装修应用 v1.0
```

## 🔄 版本历史

### v1.0 (当前版本)
- ✅ 重构为单家具选择模式
- ✅ 实现画笔涂画功能
- ✅ 集成千问图像融合API
- ✅ 添加Mask图片生成和保存
- ✅ 优化用户界面和交互体验

### v0.2 (历史版本)
- 多家具选择和拖拽定位
- 图片合并和位置追踪
- 异步API调用

## 📞 技术支持

如遇到问题，请查看：
1. 项目日志文件
2. 浏览器开发者工具
3. API响应错误信息

---

**AI智能家装系统 v1.0** - 让装修设计更简单、更智能！