# AI装修应用项目结构文档

## 项目概述
AI智能家装应用，基于Flask框架，集成阿里云千问图像融合API，实现客厅图片+家具选择+mask涂抹的智能装修效果图生成。

## 🚀 核心启动文件

### `src/app.py` ⭐ **主要启动文件**
- **用途**: 生产环境主应用入口
- **功能**: 
  - Flask Web服务器
  - 千问图像融合API集成
  - 用户图片上传处理
  - Mask图片生成和透明度处理
  - 装修效果图生成
- **启动方式**: `python src/app.py`
- **端口**: 5000
- **依赖**: 需要安装 `dashscope` 库和配置API密钥

## 📁 项目目录结构

```
AI_DECORATION/
├── 🔥 核心应用文件
│   ├── src/
│   │   ├── app.py                    ⭐ 主应用入口（生产环境）
│   │   ├── app_temp.py               🔧 调试版本（开发测试用）
│   │   └── templates/
│   │       ├── index_v1.html         ⭐ 主界面模板（与app.py配套）
│   │       ├── index.html            📋 旧版界面（已废弃）
│   │       └── mask_generator.html   🔧 独立mask生成器
│   │
├── 🗂️ 数据存储目录
│   ├── data/
│   │   ├── furniture/                ⭐ 家具库图片（必需）
│   │   │   ├── sofa_1.jpg           ⭐ 沙发样本1
│   │   │   └── sofa_2.jpg           ⭐ 沙发样本2
│   │   ├── user/                    ⭐ 用户上传图片存储
│   │   ├── masks/                   ⭐ 生成的mask图片存储
│   │   └── output/                  ⭐ 最终生成效果图存储
│   │
├── 📋 配置文件
│   ├── requirements.txt             ⭐ Python依赖列表
│   ├── .env                         ⭐ 环境变量配置（API密钥）
│   └── .gitignore                   📋 Git忽略文件
│   
├── 🔧 开发辅助文件
│   ├── start_v1.bat                 🔧 Windows启动脚本
│   ├── start_debug.bat              🔧 调试模式启动脚本
│   └── run_test.bat                 🔧 测试运行脚本
│   
├── 📊 日志和调试
│   ├── project_log/                 📊 应用运行日志
│   ├── debug/                       🔧 调试数据存储（仅app_temp.py使用）
│   └── prompt_log/                  📊 API调用日志
│   
├── 🧪 测试文件（可删除）
│   ├── test/                        ❌ 各种测试脚本和样本
│   ├── verify_*.py                  ❌ 项目验证脚本
│   ├── test_*.py                    ❌ 单元测试文件
│   └── quick_fix_test.py            ❌ 快速修复测试
│   
├── 📚 文档文件
│   ├── README.md                    📚 项目说明
│   ├── README_v1.0.md              📚 v1.0版本说明
│   ├── 项目开发需求/                 📚 需求文档目录
│   └── *.md                         📚 各种开发文档
│   
└── 🔧 辅助工具（可选）
    ├── mask_generator.py            🔧 独立mask生成工具
    ├── start_mask_generator.py      🔧 mask生成器启动脚本
    └── ref_info/                    🔧 参考代码和示例
```

## 🎯 与 `src/app.py` 直接相关的核心文件

### 必需文件 ⭐
1. **`src/app.py`** - 主应用文件
2. **`src/templates/index_v1.html`** - 前端界面模板
3. **`requirements.txt`** - Python依赖
4. **`.env`** - 环境变量配置
5. **`data/furniture/`** - 家具库图片目录
6. **`data/user/`** - 用户上传图片存储
7. **`data/masks/`** - mask图片存储
8. **`data/output/`** - 生成结果存储
9. **`project_log/`** - 应用日志存储

### 可选文件 🔧
1. **`start_v1.bat`** - Windows启动脚本
2. **`客厅.jpg`** - 测试用客厅图片样本

## 📦 依赖关系分析

### Python包依赖
```
Flask==2.3.3           # Web框架
Pillow==10.0.1         # 图像处理
python-dotenv==1.0.0   # 环境变量管理
dashscope>=1.23.8      # 阿里云千问API
requests>=2.31.0       # HTTP请求（下载生成图片）
Werkzeug>=2.3.7        # Flask底层工具
```

### 环境变量依赖
```bash
DASHSCOPE_API_KEY=sk-xxx  # 千问API密钥（必需）
```

## 🗑️ 可以删除的文件/目录

### 测试和开发文件 ❌
```
test/                          # 整个测试目录
verify_project.py             # 项目验证脚本
verify_v0.2_update.py         # 版本验证脚本
run_tests.py                  # 测试运行器
quick_fix_test.py             # 快速测试脚本
test_*.py                     # 所有测试文件
```

### 调试和临时文件 ❌
```
src/app_temp.py               # 调试版本应用
debug/                        # 调试数据目录
start_debug.bat              # 调试启动脚本
```

### 辅助工具 ❌
```
mask_generator.py             # 独立mask生成器
start_mask_generator.py       # mask生成器启动脚本
src/templates/mask_generator.html  # mask生成器模板
ref_info/                     # 参考代码目录
```

### 文档文件 ❌（生产环境可删除）
```
README.md                     # 项目说明
README_v1.0.md               # 版本说明
项目开发需求/                  # 需求文档目录
*.md                          # 各种markdown文档
TROUBLESHOOTING.md            # 故障排除文档
UPDATE_*.md                   # 更新说明文档
```

### 旧版本文件 ❌
```
src/templates/index.html      # 旧版界面模板
start.py                      # 旧版启动脚本
```

## 🚀 最小化部署清单

### 生产环境必需文件
```
AI_DECORATION/
├── src/
│   ├── app.py                # 主应用
│   └── templates/
│       └── index_v1.html     # 界面模板
├── data/
│   ├── furniture/            # 家具库（含样本图片）
│   ├── user/                 # 用户上传目录（空）
│   ├── masks/                # mask存储目录（空）
│   └── output/               # 输出目录（空）
├── project_log/              # 日志目录（空）
├── requirements.txt          # 依赖列表
└── .env                      # 环境配置
```

### 启动命令
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
echo "DASHSCOPE_API_KEY=your_api_key_here" > .env

# 启动应用
python src/app.py
```

## 🔧 功能模块说明

### 核心功能模块
1. **图片上传处理** - 支持JPG/PNG格式，自动生成唯一文件名
2. **家具库管理** - 从`data/furniture/`读取可选家具
3. **Canvas涂抹** - 前端Canvas实现蓝色区域标记
4. **透明度处理** - 支持用户自定义透明度设置
5. **Mask图片生成** - 生成原图+蓝色涂抹的叠加图片
6. **API调用** - 集成千问图像融合API
7. **结果下载** - 自动下载并保存生成的效果图

### 技术特性
- **响应式设计** - 支持移动端和桌面端
- **实时预览** - Canvas实时显示涂抹效果
- **错误处理** - 完善的异常处理和用户提示
- **日志记录** - 详细的操作日志和调试信息
- **文件管理** - 自动创建必需目录和文件清理

## 📝 部署注意事项

1. **API密钥配置** - 确保`.env`文件中配置正确的千问API密钥
2. **目录权限** - 确保应用对`data/`目录有读写权限
3. **依赖安装** - 生产环境需要安装`dashscope`库
4. **端口配置** - 默认端口5000，可在`app.py`中修改
5. **静态文件** - 如需CDN，可将CSS/JS提取到`static/`目录
6. **数据库** - 当前版本无需数据库，所有数据存储在文件系统

---

**版本**: v1.0  
**最后更新**: 2026-01-11  
**维护状态**: 活跃开发中