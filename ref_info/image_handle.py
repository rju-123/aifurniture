import base64
import os
from http import HTTPStatus
from dashscope import ImageSynthesis
import mimetypes

"""
环境要求：
    dashscope python SDK >= 1.23.8
安装/升级SDK:
    pip install -U dashscope
"""

# 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
api_key = os.getenv("DASHSCOPE_API_KEY")



# --- 辅助函数：用于 Base64 编码 ---
# 格式为 data:{MIME_type};base64,{base64_data}
def encode_file(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("不支持或无法识别的图像格式")
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return f"data:{mime_type};base64,{encoded_string}"

"""
图像输入方式说明：
以下提供了三种图片输入方式，三选一即可

1. 使用公网URL - 适合已有公开可访问的图片
2. 使用本地文件 - 适合本地开发测试
3. 使用Base64编码 - 适合私有图片或需要加密传输的场景
"""

# 【方式一】使用公网图片 URL
mask_image_url = "http://wanx.alicdn.com/material/20250318/description_edit_with_mask_3_mask.png"
base_image_url = "http://wanx.alicdn.com/material/20250318/description_edit_with_mask_3.jpeg"

# 【方式二】使用本地文件（支持绝对路径和相对路径）
# 格式要求：file:// + 文件路径
# 示例（绝对路径）：
# mask_image_url = "file://" + "/path/to/your/mask_image.png"     # Linux/macOS
# base_image_url = "file://" + "C:/path/to/your/base_image.jpeg"  # Windows
# 示例（相对路径）：
# mask_image_url = "file://" + "./mask_image.png"                 # 以实际路径为准
# base_image_url = "file://" + "./base_image.jpeg"                # 以实际路径为准

# 【方式三】使用Base64编码的图片
# mask_image_url = encode_file("./mask_image.png")               # 以实际路径为准
# base_image_url = encode_file("./base_image.jpeg")               # 以实际路径为准


def sample_sync_call_imageedit():
    print('please wait...')
    rsp = ImageSynthesis.call(api_key=api_key,
                              model="wanx2.1-imageedit",
                              function="description_edit_with_mask",
                              prompt="陶瓷兔子拿着陶瓷小花",
                              mask_image_url=mask_image_url,
                              base_image_url=base_image_url,
                              n=1)
    assert rsp.status_code == HTTPStatus.OK

    print('response: %s' % rsp)
    if rsp.status_code == HTTPStatus.OK:
        for result in rsp.output.results:
            print("---------------------------")
            print(result.url)
    else:
        print('sync_call Failed, status_code: %s, code: %s, message: %s' %
              (rsp.status_code, rsp.code, rsp.message))


if __name__ == '__main__':
    sample_sync_call_imageedit()