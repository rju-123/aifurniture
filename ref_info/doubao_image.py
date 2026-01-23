import os
import base64
from volcenginesdkarkruntime import Ark  # 需先安装SDK：pip install 'volcengine-python-sdk[ark]'

# 1. 初始化客户端（替换为您的API Key）
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("ARK_API_KEY")  # 建议通过环境变量管理密钥
)

# 2. 本地图片转Base64编码（支持PNG/JPG/WebP等格式）
def local_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        base64_encoded = base64.b64encode(f.read()).decode("utf-8")
    # 自动识别图片格式（需保证文件扩展名与实际格式一致）
    ext = image_path.split(".")[-1].lower()
    return f"data:image/{ext};base64,{base64_encoded}"

# 3. 输入参数配置（本地图片+Prompt）
prompt = "将图1的服装风格与图2的场景融合，生成一张未来科技感的街拍图"  # 生成指令
local_image_paths = [
    "local_image1.png",  # 本地参考图1
    "local_image2.jpg"   # 本地参考图2
]
# 转换本地图片为Base64列表
image_base64_list = [local_image_to_base64(path) for path in local_image_paths]

# 4. 调用图片生成API
response = client.images.generate(
    model="doubao-seedream-4-5-251128",  # 模型ID（固定值）
    prompt=prompt,
    image=image_base64_list,  # 本地图片Base64列表（支持1-14张）
    size="2K",  # 输出分辨率（可选：2K/4K或自定义像素如"2048x1536"）
    response_format="url",  # 输出格式：url/b64_json
    watermark=False  # 是否添加水印（默认True）
)

# 5. 处理响应结果
if response.data:
    generated_image_url = response.data[0].url
    print(f"生成图片URL：{generated_image_url}")
else:
    print(f"请求失败：{response.error}")
