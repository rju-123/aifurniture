# 智能家装效果生成系统

一个基于Flask和千问大模型的智能家装效果图生成系统，用户可以上传客厅照片，选择家具并拖放到合适位置，系统将自动生成真实的装修效果图。

## 功能特性

- 📷 **图片上传**: 支持JPG、PNG、GIF格式，最大16MB
- 🪑 **家具选择**: 从家具库中选择各类家具
- 🎨 **拖放编辑**: 直观的拖放界面，自由摆放家具
- 🤖 **AI生成**: 基于千问大模型生成真实的装修效果图
- 📱 **响应式设计**: 支持桌面和移动设备

## 🔧 配置位置说明

### Prompt模板配置
- **文件位置**: `src/app.py`
- **函数**: `generate_decoration()`
- **行数**: 约第179-191行
- **配置内容**: 
  ```python
  prompt = f"""
  请根据以下信息生成一张真实的客厅家装效果图：
  原始客厅图片：{{data\\user\\{data.get('original_image', '')}}}
  用户选择的家具：{data.get('furniture_selections', [])}
  家具摆放位置：{data.get('furniture_positions', [])}
  
  要求：
  1. 客厅的原始图片不要做任何变动
  2. 家具的外形不要做任何变化、但为了美观，可以适当调整家具的摆放位置、角度、大小。自然地融入到指定位置
  3. 确保家具的比例、光影、透视都符合真实场景
  4. 整体效果要协调美观
  """
  ```

### 模型配置
- **API配置文件**: `.env`
- **配置项**:
  ```env
  QIANWEN_API_KEY=your-api-key-here
  QIANWEN_API_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis
  ```
- **模型参数位置**: `src/app.py` 第193-205行
  ```python
  request_data = {
      "model": "wanx-v1",
      "input": {
          "prompt": prompt,
          "negative_prompt": "模糊, 变形, 不真实, 低质量",
          "style": "<photography>",
          "size": "1024*1024",
          "ref_img": f"data:image/jpeg;base64,{image_base64}"
      }
  }
  ```

### 图像处理配置
- **编码函数位置**: `src/app.py` 第60-70行
- **图像传递方式**: Base64编码 + 参考图像模式
- **支持格式**: JPG, PNG, GIF

## 项目结构

```
AI_DECORATION/
├── src/                    # 源代码目录
│   ├── app.py             # Flask主应用 (包含prompt和模型配置)
│   ├── templates/         # HTML模板
│   │   └── index.html     # 主页面
│   └── static/            # 静态资源
│       ├── css/
│       │   └── style.css  # 样式文件
│       └── js/
│           └── app.js     # 前端JavaScript
├── data/                  # 数据目录
│   ├── user/             # 用户上传的客厅图片
│   ├── user_input/       # 用户输入数据
│   ├── furniture/        # 家具图片库
│   └── output/           # 生成的效果图
├── test/                 # 测试脚本
│   ├── test_app.py       # 应用测试
│   └── test_integration.py # 集成测试
├── prompt_log/           # 大模型调用日志
├── project_log/          # 项目运行日志
├── requirements.txt      # Python依赖
├── .env                  # 环境配置 (API密钥配置)
└── README.md            # 项目说明
```

## 安装和配置

### 1. 环境要求

- Python 3.10+
- Anaconda (推荐)

### 2. 创建Python环境

```bash
# 使用Anaconda创建Python 3.10环境
conda create -n ai_decoration python=3.10
conda activate ai_decoration
```

### 3. 安装依赖

```bash
# 安装Python包
pip install -r requirements.txt
```

### 4. 配置环境变量

编辑 `.env` 文件，配置千问API密钥：

```env
# 千问大模型API配置
QIANWEN_API_KEY=your-qianwen-api-key-here
QIANWEN_API_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis

# Flask应用配置
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
```

### 5. 准备家具库

在 `data/furniture/` 目录中添加家具图片，支持的格式：
- JPG/JPEG
- PNG
- GIF

建议的家具分类：
- 沙发类：sofa_*.jpg
- 桌子类：table_*.jpg  
- 椅子类：chair_*.jpg
- 柜子类：cabinet_*.jpg
- 装饰品：decoration_*.jpg

## 使用方法

### 1. 启动应用

```bash
# 方式1：使用启动脚本（推荐）
python start.py

# 方式2：直接启动Flask应用
cd src
python app.py
```

应用将在 `http://localhost:5000` 启动。

### 2. 使用流程

1. **上传客厅照片**
   - 点击"选择文件"或拖拽图片到上传区域
   - 支持JPG、PNG、GIF格式，最大16MB
   - 系统会自动将图片编码为base64格式传递给AI模型

2. **选择家具**
   - 浏览家具库，点击选择需要的家具
   - 可以按分类筛选家具

3. **拖放摆放**
   - 在画布上拖放家具到合适位置
   - 可以调整家具的大小和角度
   - 支持删除和重新摆放

4. **生成效果图**
   - 点击"生成效果图"按钮
   - 系统使用**参考图像模式**调用千问大模型
   - **新特性**：AI能够理解原始客厅图像内容，生成更准确的效果
   - 生成时间约30-60秒，完成后可以下载图片

### 3. 最新调用方式（v0.2更新）

#### 图像处理方式
```python
# 新的图像传递方式：Base64编码 + 参考图像
def encode_image_to_base64(image_path):
    """将图像文件编码为base64字符串"""
    with open(image_path, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string

# API调用时使用参考图像
request_data = {
    "model": "wanx-v1",
    "input": {
        "prompt": prompt,
        "negative_prompt": "模糊, 变形, 不真实, 低质量",
        "style": "<photography>",
        "size": "1024*1024",
        "ref_img": f"data:image/jpeg;base64,{image_base64}"  # 关键改进
    }
}
```

#### 当前Prompt模板
```python
prompt = f"""
请根据以下信息生成一张真实的客厅家装效果图：
原始客厅图片：{{data\\user\\{data.get('original_image', '')}}}
用户选择的家具：{data.get('furniture_selections', [])}
家具摆放位置：{data.get('furniture_positions', [])}

要求：
1. 客厅的原始图片不要做任何变动
2. 家具的外形不要做任何变化、但为了美观，可以适当调整家具的摆放位置、角度、大小。自然地融入到指定位置
3. 确保家具的比例、光影、透视都符合真实场景
4. 整体效果要协调美观
"""
```

### 4. API接口

#### 上传图片
```http
POST /upload
Content-Type: multipart/form-data

参数：
- file: 图片文件

返回：
{
  "success": true,
  "filename": "unique_filename.jpg",
  "message": "图片上传成功"
}
```

#### 获取家具列表
```http
GET /furniture

返回：
{
  "furniture": [
    {
      "name": "sofa.jpg",
      "path": "/furniture/sofa.jpg"
    }
  ]
}
```

#### 生成效果图
```http
POST /generate
Content-Type: application/json

参数：
{
  "original_image": "filename.jpg",
  "furniture_selections": [...],
  "furniture_positions": [...]
}

返回：
{
  "success": true,
  "generated_image": "/output/generated_xxx.jpg",
  "message": "家装效果图生成成功"
}
```

## 测试

### 运行单元测试

```bash
# 运行应用测试
python test/test_app.py

# 运行集成测试（需要先启动应用）
python test/test_integration.py
```

### 测试覆盖

- ✅ 图片上传功能
- ✅ 家具列表获取
- ✅ 用户输入保存
- ✅ 千问API集成
- ✅ 文件服务
- ✅ 错误处理

## 日志系统

### 大模型调用日志
位置：`prompt_log/prompt_YYYYMMDD_HHMMSS.json`

记录内容：
- 请求时间戳
- 用户输入数据
- API请求参数
- API响应结果

### 项目运行日志
位置：`project_log/project.log`

记录内容：
- 用户操作记录
- 错误信息
- 系统状态

## 故障排除

### 常见问题

1. **千问API调用失败**
   - 检查API密钥是否正确配置
   - 确认网络连接正常
   - 查看API配额是否充足

2. **图片上传失败**
   - 检查文件格式是否支持
   - 确认文件大小不超过16MB
   - 检查data/user目录权限

3. **家具库为空**
   - 在data/furniture目录添加家具图片
   - 确保图片格式正确（JPG/PNG/GIF）

4. **生成效果图失败**
   - 检查千问API配置
   - 查看prompt_log中的错误信息
   - 确认用户输入数据完整

### 性能优化

1. **图片处理优化**
   - 压缩上传图片大小
   - 使用适当的图片格式
   - 启用图片缓存

2. **API调用优化**
   - 合理设置超时时间
   - 实现重试机制
   - 监控API使用量

## 开发说明

### 技术栈

- **后端**: Flask, Python 3.10
- **前端**: HTML5, CSS3, JavaScript, Fabric.js
- **AI模型**: 千问文生图API
- **图片处理**: Pillow (PIL)

### 扩展功能

可以考虑添加的功能：
- 用户账户系统
- 历史记录管理
- 更多家具分类
- 3D效果预览
- 社交分享功能

### 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件

---

**注意**: 使用本系统需要配置有效的千问API密钥。请确保遵守相关服务条款和使用限制。