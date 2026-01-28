from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import uuid
import time
from datetime import datetime
import json
import base64
import mimetypes
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw
import io
from dotenv import load_dotenv
import requests

# 尝试导入豆包SDK
try:
    from volcenginesdkarkruntime import Ark
    DOUBAO_AVAILABLE = True
except ImportError:
    DOUBAO_AVAILABLE = False
    print("警告: 豆包SDK未安装，图像生成功能将不可用")

# 尝试导入通义千问SDK
try:
    from dashscope import MultiModalConversation
    import dashscope
    DASHSCOPE_AVAILABLE = True
    # 设置API地址（中国北京地域）
    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
except ImportError:
    DASHSCOPE_AVAILABLE = False
    print("警告: DashScope SDK未安装，图像修复功能将不可用")

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 全局错误处理器 - 确保所有错误都返回JSON格式
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """处理所有未捕获的异常，确保返回JSON格式"""
    log_project(f"未捕获的异常: {str(e)}")
    return jsonify({'error': 'An error occurred', 'message': str(e)}), 500

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 配置文件夹路径
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'data', 'user')
app.config['FURNITURE_FOLDER'] = os.path.join(BASE_DIR, 'data', 'furniture')
app.config['OUTPUT_FOLDER'] = os.path.join(BASE_DIR, 'data', 'output')
app.config['MASK_FOLDER'] = os.path.join(BASE_DIR, 'data', 'masks')  # 新增：存储mask图片
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 确保必要的目录存在（在模块加载时执行，适用于 Gunicorn）
# 这样无论是直接运行还是通过 Gunicorn 启动，目录都会被创建
for folder in [
    app.config['UPLOAD_FOLDER'],
    app.config['FURNITURE_FOLDER'],
    app.config['OUTPUT_FOLDER'],
    app.config['MASK_FOLDER'],
    os.path.join(BASE_DIR, 'project_log')
]:
    try:
        os.makedirs(folder, exist_ok=True)
        print(f"✓ 确保目录存在: {folder}")
    except Exception as e:
        print(f"✗ 创建目录失败 {folder}: {str(e)}")

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_path, max_size_mb=1.0, quality=85):
    """
    压缩图片到指定大小以下
    
    参数:
        image_path: 图片文件路径
        max_size_mb: 最大文件大小（MB），默认1MB
        quality: JPEG质量（1-100），默认85
    
    返回:
        bool: 是否进行了压缩
    """
    max_size_bytes = max_size_mb * 1024 * 1024  # 转换为字节
    
    # 检查文件大小
    if not os.path.exists(image_path):
        return False
    
    file_size = os.path.getsize(image_path)
    if file_size <= max_size_bytes:
        log_project(f"图片大小 {file_size/1024/1024:.2f}MB，无需压缩")
        return False
    
    log_project(f"图片大小 {file_size/1024/1024:.2f}MB，开始压缩...")
    
    try:
        # 打开图片
        with Image.open(image_path) as img:
            # 转换为RGB模式（JPEG不支持透明度）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 获取原始尺寸
            original_size = img.size
            original_quality = quality
            
            # 尝试不同的压缩策略
            temp_path = image_path + '.tmp'
            
            # 策略1: 先尝试只调整质量
            for q in range(quality, 20, -10):  # 从85降到20，每次减10
                img.save(temp_path, 'JPEG', quality=q, optimize=True)
                if os.path.getsize(temp_path) <= max_size_bytes:
                    os.replace(temp_path, image_path)
                    log_project(f"压缩成功: {file_size/1024/1024:.2f}MB -> {os.path.getsize(image_path)/1024/1024:.2f}MB (质量={q})")
                    return True
            
            # 策略2: 如果质量压缩不够，调整尺寸
            scale_factor = 0.9
            current_size = original_size
            
            while scale_factor >= 0.5:  # 最小缩放到50%
                new_size = (int(original_size[0] * scale_factor), int(original_size[1] * scale_factor))
                resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # 尝试不同的质量
                for q in range(quality, 30, -10):
                    resized_img.save(temp_path, 'JPEG', quality=q, optimize=True)
                    if os.path.getsize(temp_path) <= max_size_bytes:
                        os.replace(temp_path, image_path)
                        log_project(f"压缩成功: {file_size/1024/1024:.2f}MB -> {os.path.getsize(image_path)/1024/1024:.2f}MB (尺寸={new_size}, 质量={q})")
                        return True
                
                scale_factor -= 0.1
            
            # 如果还是太大，使用最小尺寸和最低质量
            min_size = (int(original_size[0] * 0.5), int(original_size[1] * 0.5))
            final_img = img.resize(min_size, Image.Resampling.LANCZOS)
            final_img.save(temp_path, 'JPEG', quality=30, optimize=True)
            os.replace(temp_path, image_path)
            
            final_size = os.path.getsize(image_path)
            log_project(f"压缩完成: {file_size/1024/1024:.2f}MB -> {final_size/1024/1024:.2f}MB (最小尺寸={min_size}, 质量=30)")
            return True
            
    except Exception as e:
        log_project(f"图片压缩失败: {str(e)}")
        # 如果压缩失败，删除临时文件
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False

def log_project(message):
    """记录项目日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_dir = os.path.join(BASE_DIR, 'project_log')
    log_file = os.path.join(log_dir, 'project.log')
    
    # 确保日志目录存在（双重保险）
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"[警告] 无法创建日志目录 {log_dir}: {str(e)}")
        return
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        # 如果日志写入失败，至少打印到控制台
        print(f"[日志写入失败] [{timestamp}] {message}")
        print(f"[错误] {str(e)}")

def compress_image_for_api(image_path, max_dimension=1024):
    """
    为API调用压缩图片，限制像素尺寸在指定范围内
    
    参数:
        image_path: 图片文件路径
        max_dimension: 最大像素尺寸（宽或高的最大值），默认1024
    
    返回:
        str: 压缩后的图片路径（如果压缩了，可能是临时文件路径；否则返回原路径）
        bool: 是否进行了压缩
    """
    if not os.path.exists(image_path):
        return image_path, False
    
    try:
        with Image.open(image_path) as img:
            original_size = img.size
            original_width, original_height = original_size
            max_original_dimension = max(original_width, original_height)
            
            # 检查是否需要压缩尺寸
            if max_original_dimension <= max_dimension:
                log_project(f"图片尺寸符合要求: {original_width}x{original_height}，无需压缩")
                return image_path, False
            
            log_project(f"开始压缩图片用于API: 原始尺寸={original_width}x{original_height}，目标最大尺寸={max_dimension}")
            
            # 计算缩放比例
            scale = max_dimension / max_original_dimension
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            log_project(f"压缩像素尺寸: {original_width}x{original_height} -> {new_width}x{new_height}")
            
            # 先缩放图片
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为RGB模式（JPEG不支持透明度）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', (new_width, new_height), (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                # 粘贴到白色背景上
                if img.mode == 'RGBA':
                    background.paste(img, (0, 0), img.split()[-1])
                else:
                    background.paste(img, (0, 0))
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 保存压缩后的图片（使用临时文件，避免覆盖原文件）
            temp_path = image_path + '.api_compressed.jpg'
            img.save(temp_path, 'JPEG', quality=85, optimize=True)
            
            compressed_size = os.path.getsize(temp_path)
            log_project(f"压缩完成: 像素尺寸={new_width}x{new_height}, 文件大小={compressed_size/1024/1024:.2f}MB")
            
            return temp_path, True
                
    except Exception as e:
        log_project(f"图片压缩失败: {str(e)}")
        import traceback
        log_project(f"压缩错误堆栈:\n{traceback.format_exc()}")
        return image_path, False

def encode_file_to_base64(file_path):
    """将本地图片文件转换为 Base64 Data URL（优化内存使用）"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"图片文件不存在: {file_path}")
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("不支持或无法识别的图像格式")
    
    # 检查文件大小，对大文件发出警告
    file_size = os.path.getsize(file_path)
    if file_size > 10 * 1024 * 1024:  # 10MB
        log_project(f"警告: 文件较大 ({file_size/1024/1024:.2f}MB)，Base64编码可能占用约 {file_size*1.33/1024/1024:.2f}MB 内存")
    
    # 读取文件并编码（注意：base64.b64encode需要完整数据，无法流式处理）
    with open(file_path, "rb") as image_file:
        file_data = image_file.read()
        encoded_string = base64.b64encode(file_data).decode('utf-8')
        # 立即释放file_data引用，帮助GC回收
        del file_data
    
    return f"data:{mime_type};base64,{encoded_string}"

def calculate_sofa_size_range(room_length, room_width):
    """
    计算适合摆放沙发的尺寸范围
    
    参数:
        room_length: 客厅长度（米）
        room_width: 客厅宽度（米）
    
    返回:
        dict: 包含 sofa_length_min, sofa_length_max, sofa_width_min, sofa_width_max
    """
    # 沙发长度：最大值 = 客厅长度 × 0.6，但不超过 3.5米
    #           最小值 = 客厅长度 × 0.3，但不小于 1米
    sofa_length_max = min(room_length * 0.6, 3.5)
    sofa_length_min = max(room_length * 0.3, 1.0)
    
    # 沙发宽度：最大值 = 客厅宽度 × 0.3，但不超过 1米
    #           最小值 = 客厅宽度 × 0.2，但不超过 0.7米
    sofa_width_max = min(room_width * 0.3, 1.0)
    sofa_width_min = min(room_width * 0.2, 0.7)
    
    return {
        'sofa_length_min': sofa_length_min,
        'sofa_length_max': sofa_length_max,
        'sofa_width_min': sofa_width_min,
        'sofa_width_max': sofa_width_max
    }


def call_baidu_room_size_api(image_path):
    """
    调用百度智能云API识别客厅尺寸
    
    参数:
        image_path: 图片文件路径
    
    返回:
        dict: {
            'success': bool,
            'length': float,  # 长度（米）
            'width': float,   # 宽度（米）
            'error': str     # 错误信息（如果失败）
        }
    """
    try:
        # ========== 步骤1: 检查API配置 ==========
        api_key = os.getenv("BAIDU_API_KEY")
        secret_key = os.getenv("BAIDU_SECRET_KEY")
        
        log_project("=" * 80)
        log_project("【调试】开始调用百度智能云API")
        log_project(f"【调试】API Key存在: {bool(api_key)}")
        log_project(f"【调试】Secret Key存在: {bool(secret_key)}")
        
        if not api_key or not secret_key:
            error_msg = '未配置百度智能云API密钥，请在.env文件中配置BAIDU_API_KEY和BAIDU_SECRET_KEY'
            log_project(f"【错误】{error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # ========== 步骤2: 读取图片并获取像素尺寸 ==========
        log_project(f"【调试】读取图片文件: {image_path}")
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            image_data = base64.b64encode(image_bytes).decode('utf-8')
        log_project(f"【调试】图片大小: {len(image_bytes)} bytes")
        log_project(f"【调试】Base64编码后长度: {len(image_data)} 字符")
        
        # 获取图片的像素尺寸（用于后续的像素到物理尺寸转换）
        image_pixel_width = None
        image_pixel_height = None
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                image_pixel_width = img.width
                image_pixel_height = img.height
                log_project(f"【调试】图片像素尺寸: {image_pixel_width}x{image_pixel_height} 像素")
        except Exception as e:
            log_project(f"【警告】无法读取图片像素尺寸: {str(e)}")
        
        # ========== 步骤3: 获取Access Token ==========
        log_project("【调试】开始获取Access Token...")
        token_url = "https://aip.baidubce.com/oauth/2.0/token"
        token_params = {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key
        }
        
        log_project(f"【调试】Token请求URL: {token_url}")
        log_project(f"【调试】Token请求参数: grant_type=client_credentials, client_id={api_key[:10]}...")
        
        token_response = requests.post(token_url, params=token_params, timeout=10)
        log_project(f"【调试】Token响应状态码: {token_response.status_code}")
        
        try:
            token_data = token_response.json()
        except Exception as e:
            log_project(f"【错误】Token响应JSON解析失败: {str(e)}")
            log_project(f"【错误】Token响应原始内容: {token_response.text[:500]}")
            return {
                'success': False,
                'error': f'Token响应解析失败: {str(e)}'
            }
        
        log_project(f"【调试】Token响应完整数据: {json.dumps(token_data, ensure_ascii=False, indent=2)}")
        
        # 检查Token获取是否成功
        if 'access_token' not in token_data:
            error_code = token_data.get('error_code', '未知')
            error_msg_token = token_data.get('error_description', token_data.get('error', '未知错误'))
            log_project(f"【错误】获取access_token失败!")
            log_project(f"【错误】错误码: {error_code}")
            log_project(f"【错误】错误信息: {error_msg_token}")
            log_project(f"【错误】完整响应: {json.dumps(token_data, ensure_ascii=False, indent=2)}")
            
            # 常见错误码说明
            if error_code == 110:
                error_msg = "Access Token获取失败: API Key无效或已过期 (错误码: 110)"
            elif error_code == 111:
                error_msg = "Access Token获取失败: Secret Key无效或已过期 (错误码: 111)"
            else:
                error_msg = f"获取access_token失败: {error_msg_token} (错误码: {error_code})"
            
            return {
                'success': False,
                'error': error_msg
            }
        
        access_token = token_data['access_token']
        expires_in = token_data.get('expires_in', '未知')
        log_project(f"【成功】Access Token获取成功!")
        log_project(f"【调试】Token长度: {len(access_token)} 字符")
        log_project(f"【调试】Token有效期: {expires_in} 秒")
        log_project(f"【调试】Token前10字符: {access_token[:10]}...")
        
        # ========== 步骤4: 调用物体检测API ==========
        log_project("【调试】开始调用百度物体检测API...")
        api_url = f"https://aip.baidubce.com/rest/2.0/image-classify/v1/object_detect?access_token={access_token}"
        log_project(f"【调试】API端点: {api_url}")
        log_project(f"【调试】使用的API: 百度智能云 - 物体检测API (object_detect)")
        log_project(f"【调试】API说明: 该API返回检测到的物体信息，不直接返回房间尺寸")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'image': image_data
        }
        
        log_project(f"【调试】发送API请求...")
        log_project(f"【调试】请求头: {headers}")
        log_project(f"【调试】请求数据大小: {len(data['image'])} 字符 (Base64)")
        
        response = requests.post(api_url, headers=headers, data=data, timeout=30)
        log_project(f"【调试】API响应状态码: {response.status_code}")
        log_project(f"【调试】API响应头: {dict(response.headers)}")
        
        # ========== 步骤5: 解析API响应 ==========
        try:
            result = response.json()
        except Exception as e:
            log_project(f"【错误】API响应JSON解析失败: {str(e)}")
            log_project(f"【错误】API响应原始内容 (前1000字符): {response.text[:1000]}")
            return {
                'success': False,
                'error': f'API响应解析失败: {str(e)}'
            }
        
        # ========== 步骤6: 打印完整的原始响应 ==========
        log_project("=" * 80)
        log_project("【重要】百度API返回的完整原始JSON数据 (Raw Response):")
        log_project("=" * 80)
        log_project(json.dumps(result, ensure_ascii=False, indent=2))
        log_project("=" * 80)
        
        # 同时打印到控制台（如果Flask在调试模式）
        print("\n" + "=" * 80)
        print("【重要】百度API返回的完整原始JSON数据 (Raw Response):")
        print("=" * 80)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("=" * 80 + "\n")
        
        # ========== 步骤7: 检查API错误 ==========
        log_project("【调试】检查API返回的错误码...")
        
        if 'error_code' in result:
            error_code = result['error_code']
            error_msg_api = result.get('error_msg', '未知错误')
            
            log_project(f"【调试】检测到错误码: {error_code}")
            log_project(f"【调试】错误信息: {error_msg_api}")
            
            # 常见错误码说明
            error_explanations = {
                110: "Access Token无效或已过期",
                111: "Access Token无效或已过期",
                100: "参数错误",
                282000: "内部服务错误",
                282001: "请求参数错误",
                282002: "请求超时",
                282003: "系统错误",
                282004: "图片格式错误",
                282005: "图片大小错误",
            }
            
            explanation = error_explanations.get(error_code, "未知错误")
            log_project(f"【错误】错误码说明: {explanation}")
            
            if error_code != 0:
                full_error_msg = f"百度API调用失败: {error_msg_api} (错误码: {error_code} - {explanation})"
                log_project(f"【错误】{full_error_msg}")
                return {
                    'success': False,
                    'error': full_error_msg,
                    'error_code': error_code,
                    'detected_objects': []
                }
        
        log_project("【调试】API调用成功，开始解析返回数据...")
        
        # ========== 步骤8: 解析返回数据结构 ==========
        log_project("【调试】分析API返回的数据结构...")
        log_project(f"【调试】返回数据的顶级键: {list(result.keys())}")
        
        # 物体检测API返回格式通常是：
        # {
        #   "result": [
        #     {
        #       "name": "物体名称",
        #       "score": 置信度,
        #       "location": {"left": x, "top": y, "width": w, "height": h}
        #     }
        #   ]
        # }
        
        # 提取检测到的物体
        detected_objects = []
        
        # 尝试多种可能的JSON结构
        log_project("【调试】尝试从不同位置提取物体数据...")
        result_data = result.get('result', [])
        log_project(f"【调试】result字段类型: {type(result_data)}, 值: {result_data}")
        
        if not result_data or not isinstance(result_data, list):
            result_data = result.get('data', {}).get('result', [])
            log_project(f"【调试】尝试data.result字段: {type(result_data)}, 值: {result_data}")
        
        if not result_data or not isinstance(result_data, list):
            result_data = result.get('objects', [])
            log_project(f"【调试】尝试objects字段: {type(result_data)}, 值: {result_data}")
        
        if isinstance(result_data, list):
            log_project(f"【调试】找到物体列表，共 {len(result_data)} 个物体")
            for idx, obj in enumerate(result_data):
                if isinstance(obj, dict):
                    obj_info = {
                        'name': obj.get('name', obj.get('type', '未知物体')),
                        'score': obj.get('score', obj.get('confidence', 0)),
                        'location': obj.get('location', obj.get('bbox', {}))
                    }
                    detected_objects.append(obj_info)
                    log_project(f"【调试】物体 {idx+1}: {obj_info['name']} (置信度: {obj_info['score']})")
        else:
            log_project(f"【警告】未找到物体列表，result_data类型: {type(result_data)}")
        
        log_project(f"【调试】最终提取到 {len(detected_objects)} 个物体")
        if detected_objects:
            log_project(f"【调试】物体列表: {[obj['name'] for obj in detected_objects]}")
        
        # 物体检测API不直接返回房间尺寸，需要基于检测结果估算
        # 查找可能的参考物（门、窗户、已知尺寸的家具等）
        reference_objects = ['门', 'door', '窗', 'window', '沙发', 'sofa', '桌子', 'table']
        found_references = [obj for obj in detected_objects 
                          if any(ref in obj['name'].lower() for ref in reference_objects)]
        
        # ========== 步骤9: 尝试提取房间尺寸 ==========
        log_project("【调试】尝试从API返回中提取房间尺寸...")
        length = None
        width = None
        
        # 方式1: 直接字段
        log_project("【调试】方式1: 检查顶级字段 length/width...")
        if 'length' in result:
            length = result['length']
            log_project(f"【调试】找到 length: {length}")
        if 'width' in result:
            width = result['width']
            log_project(f"【调试】找到 width: {width}")
        
        # 方式2: 嵌套在data字段中
        if length is None or width is None:
            log_project("【调试】方式2: 检查 data 字段...")
            data_field = result.get('data', {})
            if isinstance(data_field, dict):
                log_project(f"【调试】data字段的键: {list(data_field.keys())}")
                length = length or data_field.get('length') or data_field.get('room_length')
                width = width or data_field.get('width') or data_field.get('room_width')
                if length:
                    log_project(f"【调试】从data字段找到 length: {length}")
                if width:
                    log_project(f"【调试】从data字段找到 width: {width}")
        
        # 方式3: result字段中的尺寸信息（如果result是对象而不是数组）
        if length is None or width is None:
            log_project("【调试】方式3: 检查 result 字段（如果是对象）...")
            result_field = result.get('result', {})
            if isinstance(result_field, dict):
                log_project(f"【调试】result字段的键: {list(result_field.keys())}")
                
                # 检查是否是像素坐标格式（包含top, left, width, height）
                # 这是物体检测API返回的典型格式，表示检测区域的像素坐标
                if 'top' in result_field and 'left' in result_field and 'width' in result_field and 'height' in result_field:
                    pixel_width = result_field.get('width')
                    pixel_height = result_field.get('height')
                    pixel_top = result_field.get('top')
                    pixel_left = result_field.get('left')
                    
                    log_project(f"【重要】检测到像素坐标格式!")
                    log_project(f"【信息】检测区域像素坐标: top={pixel_top}, left={pixel_left}, width={pixel_width}px, height={pixel_height}px")
                    
                    # 基于像素尺寸估算物理尺寸
                    if image_pixel_width and image_pixel_height:
                        log_project(f"【信息】开始基于像素尺寸估算物理尺寸...")
                        log_project(f"【信息】图片像素尺寸: {image_pixel_width}x{image_pixel_height} 像素")
                        
                        # 计算检测区域占图片的比例
                        detection_area_ratio = (pixel_width * pixel_height) / (image_pixel_width * image_pixel_height)
                        log_project(f"【调试】检测区域占图片比例: {detection_area_ratio:.2%}")
                        
                        # 如果检测区域占图片的大部分（>70%），认为检测到了整个房间
                        if detection_area_ratio > 0.7:
                            log_project(f"【信息】检测区域占图片{detection_area_ratio:.2%}，认为是整个房间")
                            
                            # 基于图片宽高比和常见客厅尺寸范围进行估算
                            # 常见客厅尺寸范围：3-8米（长），2.5-6米（宽）
                            detection_aspect_ratio = pixel_width / pixel_height if pixel_height > 0 else 1
                            
                            log_project(f"【调试】检测区域宽高比: {detection_aspect_ratio:.2f}")
                            
                            # 根据宽高比估算尺寸
                            # 如果宽度>高度，认为是横向房间（长>宽）
                            if detection_aspect_ratio > 1:
                                # 横向房间：常见尺寸 4-7米 x 3-5米
                                estimated_length = 4.5 + (detection_aspect_ratio - 1) * 2.5  # 4.5-7米
                                estimated_width = 3.0 + (1 - 1/detection_aspect_ratio) * 2.0  # 3-5米
                            else:
                                # 纵向房间：常见尺寸 3-5米 x 4-7米
                                estimated_length = 3.0 + (1 - detection_aspect_ratio) * 2.0  # 3-5米
                                estimated_width = 4.5 + (1/detection_aspect_ratio - 1) * 2.5  # 4.5-7米
                            
                            # 限制在合理范围内
                            estimated_length = max(3.0, min(8.0, estimated_length))
                            estimated_width = max(2.5, min(6.0, estimated_width))
                            
                            log_project(f"【估算】基于像素尺寸估算的房间尺寸: 长≈{estimated_length:.2f}米, 宽≈{estimated_width:.2f}米")
                            log_project(f"【提示】这是估算值，用户可以在界面上纠正")
                            
                            # 使用估算值
                            length = estimated_length
                            width = estimated_width
                        else:
                            log_project(f"【信息】检测区域占图片{detection_area_ratio:.2%}，可能不是整个房间")
                            log_project(f"【提示】将使用默认估算值，用户可以在界面上纠正")
                            
                            # 使用默认估算值（中等客厅）
                            length = 5.0
                            width = 4.0
                            log_project(f"【估算】使用默认估算值: 长={length}米, 宽={width}米")
                    else:
                        log_project(f"【警告】无法获取图片像素尺寸，使用默认估算值")
                        length = 5.0
                        width = 4.0
                        log_project(f"【估算】使用默认估算值: 长={length}米, 宽={width}米")
                else:
                    # 如果不是像素坐标格式，尝试提取物理尺寸字段
                    length = length or result_field.get('length') or result_field.get('room_length')
                    width = width or result_field.get('width') or result_field.get('room_width')
                    if length:
                        log_project(f"【调试】从result字段找到 length: {length}")
                    if width:
                        log_project(f"【调试】从result字段找到 width: {width}")
        
        # 方式4: 其他可能的字段名
        if length is None or width is None:
            log_project("【调试】方式4: 检查其他可能的字段名...")
            possible_length_keys = ['room_length', 'long', '长', 'length_m', 'room_length_m']
            possible_width_keys = ['room_width', 'wide', '宽', 'width_m', 'room_width_m']
            
            for key in possible_length_keys:
                if key in result:
                    length = result[key]
                    log_project(f"【调试】从字段 '{key}' 找到 length: {length}")
                    break
            
            for key in possible_width_keys:
                if key in result:
                    width = result[key]
                    log_project(f"【调试】从字段 '{key}' 找到 width: {width}")
                    break
        
        # 转换为浮点数
        log_project("【调试】转换尺寸数据为浮点数...")
        try:
            if length is not None:
                length = float(length)
                log_project(f"【调试】length转换成功: {length}")
            if width is not None:
                width = float(width)
                log_project(f"【调试】width转换成功: {width}")
        except (ValueError, TypeError) as e:
            log_project(f"【错误】尺寸数据格式错误: length={length}, width={width}, 错误: {str(e)}")
            length = None
            width = None
        
        # ========== 步骤10: 验证并返回结果 ==========
        log_project("【调试】验证尺寸数据的有效性...")
        log_project(f"【调试】length: {length}, width: {width}")
        
        # 检查result字段中是否有像素坐标（这是物体检测API的典型返回格式）
        result_field = result.get('result', {})
        has_pixel_coords = False
        pixel_info = None
        if isinstance(result_field, dict) and 'top' in result_field and 'left' in result_field:
            has_pixel_coords = True
            pixel_info = {
                'top': result_field.get('top'),
                'left': result_field.get('left'),
                'width': result_field.get('width'),
                'height': result_field.get('height')
            }
            log_project(f"【信息】API返回了像素坐标: {pixel_info}")
            log_project(f"【结论】这是检测区域的像素坐标，不是房间的物理尺寸（米）")
        
        # 验证提取到的尺寸是否是物理尺寸（米）
        # 如果值太大（>100），可能是像素值而不是米
        if length is not None and length > 100:
            log_project(f"【警告】length值过大 ({length})，可能是像素值而不是米，已过滤")
            length = None
        if width is not None and width > 100:
            log_project(f"【警告】width值过大 ({width})，可能是像素值而不是米，已过滤")
            width = None
        
        # 检查是否通过像素坐标估算得到了尺寸
        is_estimated = False
        if isinstance(result_field, dict) and 'top' in result_field and 'left' in result_field:
            if length is not None and width is not None:
                is_estimated = True
        
        if length is not None and width is not None and length > 0 and width > 0:
            if is_estimated:
                log_project("【成功】✓ 基于像素尺寸估算到房间尺寸（估算值）!")
            else:
                log_project("【成功】✓ 从API成功识别到房间尺寸!")
            
            log_project(f"【成功】房间尺寸: 长={length}米, 宽={width}米")
            
            # 计算适合摆放沙发的尺寸范围
            sofa_range = calculate_sofa_size_range(length, width)
            sofa_length_min = sofa_range['sofa_length_min']
            sofa_length_max = sofa_range['sofa_length_max']
            sofa_width_min = sofa_range['sofa_width_min']
            sofa_width_max = sofa_range['sofa_width_max']
            
            log_project(f"【信息】适合摆放的沙发尺寸范围:")
            log_project(f"【信息】  长度: {sofa_length_min:.2f} - {sofa_length_max:.2f} 米")
            log_project(f"【信息】  宽度: {sofa_width_min:.2f} - {sofa_width_max:.2f} 米")
            
            log_project("=" * 80)
            return {
                'success': True,
                'length': round(length, 2),
                'width': round(width, 2),
                'is_estimated': is_estimated,  # 标记是否为估算值
                'sofa_length_range': {
                    'min': round(sofa_length_min, 2),
                    'max': round(sofa_length_max, 2)
                },
                'sofa_width_range': {
                    'min': round(sofa_width_min, 2),
                    'max': round(sofa_width_max, 2)
                },
                'detected_objects': detected_objects,
                'reference_objects': found_references,
                'message': '已基于图片估算房间尺寸，请确认或修改' if is_estimated else '房间尺寸识别成功'
            }
        else:
            # 如果API没有返回尺寸，使用默认估算值
            log_project("【警告】API未返回有效的房间尺寸数据，使用默认估算值")
            log_project(f"【调试】length有效性: {length is not None and length > 0}")
            log_project(f"【调试】width有效性: {width is not None and width > 0}")
            
            # 使用默认估算值（中等客厅）
            default_length = 5.0
            default_width = 4.0
            
            log_project(f"【估算】使用默认估算值: 长={default_length}米, 宽={default_width}米")
            log_project(f"【提示】用户可以在界面上纠正这些值")
            
            # 计算适合摆放沙发的尺寸范围
            sofa_range = calculate_sofa_size_range(default_length, default_width)
            sofa_length_min = sofa_range['sofa_length_min']
            sofa_length_max = sofa_range['sofa_length_max']
            sofa_width_min = sofa_range['sofa_width_min']
            sofa_width_max = sofa_range['sofa_width_max']
            
            log_project(f"【信息】适合摆放的沙发尺寸范围:")
            log_project(f"【信息】  长度: {sofa_length_min:.2f} - {sofa_length_max:.2f} 米")
            log_project(f"【信息】  宽度: {sofa_width_min:.2f} - {sofa_width_max:.2f} 米")
            
            log_project("=" * 80)
            return {
                'success': True,  # 返回成功，但标记为估算值
                'length': default_length,
                'width': default_width,
                'is_estimated': True,  # 标记为估算值
                'sofa_length_range': {
                    'min': round(sofa_length_min, 2),
                    'max': round(sofa_length_max, 2)
                },
                'sofa_width_range': {
                    'min': round(sofa_width_min, 2),
                    'max': round(sofa_width_max, 2)
                },
                'detected_objects': detected_objects,
                'reference_objects': found_references if len(detected_objects) > 0 else [],
                'message': '已基于图片估算房间尺寸，请确认或修改'
            }
            
    except requests.Timeout as e:
        error_msg = f"API请求超时: {str(e)}"
        log_project(f"【错误】{error_msg}")
        log_project("=" * 80)
        return {
            'success': False,
            'error': error_msg
        }
    except requests.RequestException as e:
        error_msg = f"API请求异常: {str(e)}"
        log_project(f"【错误】{error_msg}")
        log_project("=" * 80)
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"调用百度智能云API异常: {str(e)}"
        log_project(f"【错误】{error_msg}")
        log_project(f"【错误】异常类型: {type(e).__name__}")
        import traceback
        log_project(f"【错误】异常堆栈:\n{traceback.format_exc()}")
        log_project("=" * 80)
        return {
            'success': False,
            'error': error_msg
        }

def save_mask_image(original_image_filename, mask_data):
    """保存用户绘制的mask图片 - 生成原始图片+蓝色涂抹的叠加图片"""
    try:
        # 解析base64图片数据（这是用户涂抹的纯mask数据）
        if mask_data.startswith('data:image'):
            # 移除data:image/png;base64,前缀
            base64_data = mask_data.split(',')[1]
        else:
            base64_data = mask_data
        
        # 解码base64数据
        mask_image_data = base64.b64decode(base64_data)
        
        # 先分析原始mask数据（在保存到文件之前）
        log_project(f"原始mask数据分析: 数据长度={len(mask_image_data)} bytes")
        
        # 使用PIL直接从内存分析mask数据（优化：使用逐像素访问避免加载全部像素到内存）
        try:
            with Image.open(io.BytesIO(mask_image_data)) as temp_mask:
                log_project(f"内存中mask图片: 尺寸={temp_mask.size}, 模式={temp_mask.mode}, 格式={temp_mask.format}")
                
                # 转换为RGBA进行分析
                if temp_mask.mode != 'RGBA':
                    temp_mask = temp_mask.convert('RGBA')
                
                # 优化：使用load()方法逐像素访问，避免一次性加载所有像素到内存
                width, height = temp_mask.size
                pixels_data = temp_mask.load()
                
                # 采样分析：只分析部分像素，避免处理全部像素
                sample_size = min(1000, width * height)  # 最多采样1000个像素
                step = max(1, (width * height) // sample_size)
                
                non_transparent_count = 0
                alpha_samples = []
                sample_pixels = []
                
                pixel_idx = 0
                for y in range(height):
                    for x in range(width):
                        if pixel_idx % step == 0:  # 采样
                            pixel = pixels_data[x, y]
                            if pixel[3] > 0:  # 非透明像素
                                non_transparent_count += 1
                                alpha_samples.append(pixel[3])
                                if len(sample_pixels) < 10:
                                    sample_pixels.append(pixel)
                        pixel_idx += 1
                
                log_project(f"内存分析: 图片尺寸={width}x{height}, 采样像素={len(alpha_samples)}, 非透明像素数≈{non_transparent_count * step}")
                
                if alpha_samples:
                    log_project(f"样本像素alpha值: {[p[3] for p in sample_pixels[:10]]}")
                    
                    if alpha_samples:
                        most_common_alpha = max(set(alpha_samples), key=alpha_samples.count)
                        detected_transparency = round((255 - most_common_alpha) / 255 * 100, 1)
                        log_project(f"内存分析检测到透明度: {detected_transparency}% (alpha={most_common_alpha})")
                else:
                    log_project("警告: 内存中的mask图片没有找到非透明像素!")
                    
        except Exception as e:
            log_project(f"内存mask分析失败: {str(e)}")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(original_image_filename)[0]
        
        # 1. 先保存原始的mask图片（纯蓝色区域）用于分析
        pure_mask_filename = f"{base_name}_pure_mask_{timestamp}.png"
        pure_mask_filepath = os.path.join(app.config['MASK_FOLDER'], pure_mask_filename)
        
        with open(pure_mask_filepath, 'wb') as f:
            f.write(mask_image_data)
        
        log_project(f"保存纯mask文件: {pure_mask_filename}")
        
        # 2. 生成叠加图片：原始图片 + 蓝色涂抹
        # 检查原始图片路径 - 可能在UPLOAD_FOLDER或OUTPUT_FOLDER中（擦除后的图片在OUTPUT_FOLDER）
        original_image_path = None
        
        # 先检查UPLOAD_FOLDER
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], original_image_filename)
        if os.path.exists(upload_path):
            original_image_path = upload_path
            log_project(f"从UPLOAD_FOLDER读取原始图片: {original_image_filename}")
        else:
            # 如果在UPLOAD_FOLDER中找不到，尝试OUTPUT_FOLDER（擦除后的图片在这里）
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], original_image_filename)
            if os.path.exists(output_path):
                original_image_path = output_path
                log_project(f"从OUTPUT_FOLDER读取原始图片: {original_image_filename}")
            else:
                log_project(f"错误: 无法找到原始图片: {original_image_filename} (已检查UPLOAD和OUTPUT文件夹)")
                log_project(f"UPLOAD_FOLDER路径: {upload_path}")
                log_project(f"OUTPUT_FOLDER路径: {output_path}")
                raise FileNotFoundError(f"原始图片不存在: {original_image_filename}")
        
        if original_image_path and os.path.exists(original_image_path):
            log_project(f"使用原始图片路径: {original_image_path}")
            log_project(f"原始图片文件大小: {os.path.getsize(original_image_path)} bytes")
            
            # 打开原始图片和mask图片
            with Image.open(original_image_path) as original_img:
                log_project(f"原始图片尺寸: {original_img.size}, 模式: {original_img.mode}")
                with Image.open(pure_mask_filepath) as mask_img:
                    # 确保两个图片尺寸一致
                    if original_img.size != mask_img.size:
                        log_project(f"调整mask尺寸: {mask_img.size} -> {original_img.size}")
                        mask_img = mask_img.resize(original_img.size, Image.Resampling.LANCZOS)
                    
                    # 转换为RGBA模式
                    if original_img.mode != 'RGBA':
                        original_img = original_img.convert('RGBA')
                    if mask_img.mode != 'RGBA':
                        mask_img = mask_img.convert('RGBA')
                    
                    # 优化：使用load()方法逐像素访问，避免一次性加载所有像素到内存
                    width, height = original_img.size
                    original_pixels = original_img.load()
                    mask_pixels = mask_img.load()
                    
                    # 采样分析mask的透明度信息（只分析部分像素）
                    sample_size = min(1000, width * height)
                    step = max(1, (width * height) // sample_size)
                    alpha_samples = []
                    pixel_idx = 0
                    for y in range(height):
                        for x in range(width):
                            if pixel_idx % step == 0:
                                pixel = mask_pixels[x, y]
                                if pixel[3] > 0:
                                    alpha_samples.append(pixel[3])
                            pixel_idx += 1
                    
                    avg_alpha = sum(alpha_samples) / len(alpha_samples) if alpha_samples else 0
                    transparency_percentage = round((255 - avg_alpha) / 255 * 100, 2) if avg_alpha > 0 else 100
                    
                    log_project(f"Mask透明度分析: 平均Alpha={avg_alpha:.1f}, 透明度={transparency_percentage}%")
                    
                    # 创建叠加图片 - 使用逐像素处理，避免加载全部像素到内存
                    composite_img = original_img.copy()
                    composite_pixels = composite_img.load()
                    
                    # 逐像素混合，正确处理用户设置的透明度
                    processed_count = 0
                    
                    for y in range(height):
                        for x in range(width):
                            mask_pixel = mask_pixels[x, y]
                            orig_pixel = original_pixels[x, y]
                            
                            if mask_pixel[3] == 0:  # mask像素完全透明，保持原始像素
                                composite_pixels[x, y] = orig_pixel
                            else:  # mask像素有颜色，进行透明度混合
                                processed_count += 1
                                
                                # 获取mask的alpha值（这是用户设置的透明度）
                                user_alpha = mask_pixel[3]  # 用户设置的alpha值
                                user_alpha_ratio = user_alpha / 255.0  # 转换为0-1的比例
                                
                                # Alpha混合公式: result = mask * user_alpha + original * (1 - user_alpha)
                                blended_r = int(mask_pixel[0] * user_alpha_ratio + orig_pixel[0] * (1 - user_alpha_ratio))
                                blended_g = int(mask_pixel[1] * user_alpha_ratio + orig_pixel[1] * (1 - user_alpha_ratio))
                                blended_b = int(mask_pixel[2] * user_alpha_ratio + orig_pixel[2] * (1 - user_alpha_ratio))
                                
                                # 保持原始背景的不透明度，但颜色已经混合了用户的透明度设置
                                blended_a = orig_pixel[3]  # 保持原始背景的不透明度
                                
                                composite_pixels[x, y] = (blended_r, blended_g, blended_b, blended_a)
                    
                    log_project(f"透明度处理统计: 处理了{processed_count}个mask像素")
                    
                    if alpha_samples:
                        most_common_alpha = max(set(alpha_samples), key=alpha_samples.count)
                        actual_transparency = round((255 - most_common_alpha) / 255 * 100, 1)
                        log_project(f"检测到的用户透明度设置: {actual_transparency}% (alpha={most_common_alpha})")
                    
                    # 保存叠加图片
                    composite_filename = f"{base_name}_composite_mask_{timestamp}.png"
                    composite_filepath = os.path.join(app.config['MASK_FOLDER'], composite_filename)
                    composite_img.save(composite_filepath, 'PNG')
                    
                    log_project(f"生成叠加mask图片: {composite_filename}, 保持透明度: {transparency_percentage}%")
                    log_project(f"叠加mask图片路径: {composite_filepath}")
                    log_project(f"叠加mask图片文件大小: {os.path.getsize(composite_filepath)} bytes")
                    log_project(f"叠加mask图片尺寸: {composite_img.size}, 模式: {composite_img.mode}")
                    log_project(f"原始图片文件名: {original_image_filename}, 路径: {original_image_path}")
                    log_project(f"✓ Mask图片已基于正确的原始图片生成（擦除后的场景）")
        else:
            error_msg = f"错误: 原始图片不存在，无法生成叠加mask图片"
            if original_image_path:
                error_msg += f": {original_image_path}"
            else:
                error_msg += f": {original_image_filename} (未找到文件)"
            log_project(error_msg)
            raise FileNotFoundError(error_msg)
        
        log_project(f"保存叠加mask图片: {composite_filename}")
        
        # 返回叠加图片的信息（这是要传给API的）
        return composite_filename, composite_filepath
        
    except Exception as e:
        log_project(f"保存mask图片失败: {str(e)}")
        raise e

# 豆包客户端单例（避免重复创建客户端实例导致内存泄漏）
_DOUBAO_CLIENT = None

def get_doubao_client():
    """获取豆包客户端实例（单例模式，避免内存泄漏）"""
    global _DOUBAO_CLIENT
    
    if _DOUBAO_CLIENT is None:
        if not DOUBAO_AVAILABLE:
            raise Exception("豆包SDK未安装")
        
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise Exception("未配置ARK_API_KEY环境变量")
        
        _DOUBAO_CLIENT = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=api_key
        )
        log_project("豆包客户端初始化成功（单例模式）")
    
    return _DOUBAO_CLIENT

def call_doubao_image_fusion(mask_image_path, furniture_image_path, prompt_text):
    """调用豆包图像融合API"""
    if not DOUBAO_AVAILABLE:
        raise Exception("豆包SDK未安装")
    
    # 使用全局客户端实例（单例模式）
    client = get_doubao_client()
    
    # 用于跟踪临时文件，以便后续清理
    temp_files = []
    
    try:
        # 在编码前压缩图片，限制像素尺寸在1024×1024范围内
        log_project(f"检查上传到豆包API的图片尺寸...")
        
        # 压缩mask图片（如果需要）
        mask_compressed_path, mask_compressed = compress_image_for_api(mask_image_path, max_dimension=1024)
        if mask_compressed:
            log_project(f"Mask图片已压缩: {mask_image_path} -> {mask_compressed_path}")
            temp_files.append(mask_compressed_path)
            mask_path_to_encode = mask_compressed_path
        else:
            mask_path_to_encode = mask_image_path
        
        # 压缩家具图片（如果需要）
        furniture_compressed_path, furniture_compressed = compress_image_for_api(furniture_image_path, max_dimension=1024)
        if furniture_compressed:
            log_project(f"家具图片已压缩: {furniture_image_path} -> {furniture_compressed_path}")
            temp_files.append(furniture_compressed_path)
            furniture_path_to_encode = furniture_compressed_path
        else:
            furniture_path_to_encode = furniture_image_path
        
        # 编码图片为Base64
        mask_base64 = encode_file_to_base64(mask_path_to_encode)
        furniture_base64 = encode_file_to_base64(furniture_path_to_encode)
        
        # 记录Base64数据大小
        mask_base64_size = len(mask_base64) / 1024 / 1024  # MB
        furniture_base64_size = len(furniture_base64) / 1024 / 1024  # MB
        log_project(f"Base64编码后大小 - Mask: {mask_base64_size:.2f}MB, Furniture: {furniture_base64_size:.2f}MB")
        
        log_project(f"开始调用豆包API - mask: {mask_path_to_encode}, furniture: {furniture_path_to_encode}")
        log_project(f"Prompt: {prompt_text}")
        
        # 验证mask图片内容（检查前100个字符的Base64，确保不是空图片）
        mask_preview = mask_base64[:100] if len(mask_base64) > 100 else mask_base64
        log_project(f"Mask Base64预览（前100字符）: {mask_preview}")
        log_project(f"Mask Base64总长度: {len(mask_base64)} 字符")
        
        # 调用豆包图片生成API
        # mask图片应该包含：原始场景（擦除后的场景）+ 蓝色涂抹区域
        # 这样API才能知道在哪个场景的哪个位置放置家具
        log_project(f"调用豆包API，传入2张图片：1. mask（场景+蓝色涂抹）, 2. 家具")
        response = client.images.generate(
            model="doubao-seedream-4-5-251128",  # 豆包模型ID
            prompt=prompt_text,
            image=[mask_base64, furniture_base64],  # 本地图片Base64列表：[场景+蓝色涂抹, 家具]
            size="2K",  # 输出分辨率
            response_format="url",  # 输出格式：url
            watermark=False  # 不添加水印
        )
        
        # 处理响应
        if response.data:
            # 获取生成的图片URL
            generated_images = []
            for item in response.data:
                if hasattr(item, 'url') and item.url:
                    generated_images.append(item.url)
            
            log_project(f"豆包API调用成功，生成{len(generated_images)}张图片")
            
            return {
                'success': True,
                'images': generated_images
            }
        else:
            error_msg = "豆包API返回空数据"
            log_project(f"豆包API调用失败: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
            
    except Exception as e:
        error_msg = f"豆包图像融合异常: {str(e)}"
        log_project(error_msg)
        import traceback
        log_project(f"异常堆栈:\n{traceback.format_exc()}")
        return {
            'success': False,
            'error': error_msg
        }
    finally:
        # 清理临时压缩文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    log_project(f"已清理临时文件: {temp_file}")
            except Exception as e:
                log_project(f"清理临时文件失败 {temp_file}: {str(e)}")

@app.route('/')
def index():
    """主页面 - v1.0重构版本"""
    return render_template('index_v1.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理用户上传的客厅图片，并调用百度智能云API识别尺寸"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if file and allowed_file(file.filename):
            # 确保上传目录存在（双重保险）
            upload_folder = app.config['UPLOAD_FOLDER']
            try:
                os.makedirs(upload_folder, exist_ok=True)
            except Exception as e:
                log_project(f"创建上传目录失败: {str(e)}")
                return jsonify({'error': '无法创建上传目录'}), 500
            
            # 生成唯一文件名
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            
            # 保存文件
            try:
                file.save(filepath)
                
                # 检查文件大小，如果大于1MB则压缩
                file_size = os.path.getsize(filepath)
                log_project(f"用户上传客厅图片: {unique_filename}, 大小: {file_size/1024/1024:.2f}MB")
                
                if file_size > 1024 * 1024:  # 大于1MB
                    log_project(f"图片大小超过1MB，开始压缩...")
                    compressed = compress_image(filepath, max_size_mb=1.0, quality=85)
                    if compressed:
                        new_size = os.path.getsize(filepath)
                        log_project(f"压缩完成: {file_size/1024/1024:.2f}MB -> {new_size/1024/1024:.2f}MB")
                    else:
                        log_project(f"压缩失败或未进行压缩")
                
            except Exception as e:
                log_project(f"保存文件失败: {str(e)}")
                return jsonify({'error': f'保存文件失败: {str(e)}'}), 500
            
            # 调用百度智能云API识别客厅尺寸
            size_result = call_baidu_room_size_api(filepath)
            
            response_data = {
                'success': True,
                'filename': unique_filename,
                'message': '客厅图片上传成功',
                'size_detection': size_result
            }
            
            return jsonify(response_data)
        else:
            return jsonify({'error': '不支持的文件格式'}), 400
            
    except Exception as e:
        log_project(f"上传文件错误: {str(e)}")
        return jsonify({'error': '上传失败'}), 500

# 家具元数据缓存（避免每次请求都重新读取文件）
_FURNITURE_METADATA_CACHE = None
_FURNITURE_METADATA_CACHE_TIME = None
_FURNITURE_METADATA_CACHE_TTL = 300  # 缓存5分钟（300秒）

def load_furniture_metadata(force_reload=False):
    """加载家具元数据文件（带缓存机制，避免内存泄漏）"""
    global _FURNITURE_METADATA_CACHE, _FURNITURE_METADATA_CACHE_TIME
    
    # 检查缓存是否有效
    if not force_reload and _FURNITURE_METADATA_CACHE is not None:
        if _FURNITURE_METADATA_CACHE_TIME is not None:
            current_time = time.time()
            if current_time - _FURNITURE_METADATA_CACHE_TIME < _FURNITURE_METADATA_CACHE_TTL:
                return _FURNITURE_METADATA_CACHE
    
    # 加载元数据
    metadata_path = os.path.join(app.config['FURNITURE_FOLDER'], 'furniture_metadata.json')
    
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                furniture_list = metadata.get('furniture', [])
                
                # 更新缓存
                _FURNITURE_METADATA_CACHE = furniture_list
                _FURNITURE_METADATA_CACHE_TIME = time.time()
                
                log_project(f"家具元数据加载成功，共 {len(furniture_list)} 个家具（已缓存）")
                return furniture_list
        except Exception as e:
            log_project(f"加载家具元数据文件失败: {str(e)}")
            return []
    else:
        log_project("家具元数据文件不存在，将使用文件名解析")
        return []

@app.route('/furniture')
def get_furniture_list():
    """获取家具库列表 - 支持按风格和尺寸过滤"""
    try:
        # 获取查询参数
        style = request.args.get('style', None)  # 沙发风格
        min_length = request.args.get('min_length', None, type=float)  # 最小长度（米）
        max_length = request.args.get('max_length', None, type=float)  # 最大长度（米）
        min_width = request.args.get('min_width', None, type=float)  # 最小宽度（米）
        max_width = request.args.get('max_width', None, type=float)  # 最大宽度（米）
        room_length = request.args.get('room_length', None, type=float)  # 客厅长度
        room_width = request.args.get('room_width', None, type=float)  # 客厅宽度
        
        furniture_folder = app.config['FURNITURE_FOLDER']
        furniture_list = []
        
        # 加载元数据
        metadata_list = load_furniture_metadata()
        metadata_dict = {item['filename']: item for item in metadata_list}
        
        if os.path.exists(furniture_folder):
            files = os.listdir(furniture_folder)
            
            for filename in files:
                # 跳过元数据文件本身
                if filename == 'furniture_metadata.json':
                    continue
                    
                if allowed_file(filename):
                    # 从元数据中获取信息，如果没有则使用默认值
                    metadata = metadata_dict.get(filename, {})
                    
                    furniture_style = metadata.get('style')
                    furniture_length = metadata.get('length')
                    furniture_width = metadata.get('width')
                    display_name = metadata.get('display_name', os.path.splitext(filename)[0])
                    furniture_type = metadata.get('type', 'sofa')
                    description = metadata.get('description', '')
                    
                    # 如果没有元数据，尝试从文件名解析（向后兼容）
                    if not furniture_style:
                        name_parts = os.path.splitext(filename)[0].split('_')
                        if len(name_parts) >= 2:
                            furniture_style = name_parts[1]
                    
                    furniture_item = {
                        'name': filename,
                        'path': f'/furniture/{filename}',
                        'display_name': display_name,
                        'style': furniture_style,
                        'length': furniture_length,  # 家具长度（米）
                        'width': furniture_width,     # 家具宽度（米）
                        'type': furniture_type,
                        'description': description
                    }
                    
                    # 按风格过滤
                    if style and furniture_style:
                        if furniture_style.lower() != style.lower():
                            continue
                    elif style:
                        # 如果指定了风格但没有元数据，跳过
                        continue
                    
                    # 按尺寸过滤（如果提供了房间尺寸，过滤出适合的家具）
                    if room_length and room_width:
                        # 过滤逻辑：
                        # 1. 如果家具没有尺寸信息，保留（让用户自己判断）
                        # 2. 如果家具有尺寸信息，检查是否适合房间
                        # 家具长度和宽度都应该小于房间对应尺寸的80%（留出空间）
                        if furniture_length:
                            if furniture_length > room_length * 0.8:
                                continue
                        if furniture_width:
                            if furniture_width > room_width * 0.8:
                                continue
                    
                    # 按最小/最大尺寸过滤
                    if min_length and furniture_length:
                        if furniture_length < min_length:
                            continue
                    if max_length and furniture_length:
                        if furniture_length > max_length:
                            continue
                    if min_width and furniture_width:
                        if furniture_width < min_width:
                            continue
                    if max_width and furniture_width:
                        if furniture_width > max_width:
                            continue
                    
                    furniture_list.append(furniture_item)
        
        log_project(f"返回家具列表，共 {len(furniture_list)} 个家具 (风格={style}, 房间尺寸={room_length}x{room_width})")
        return jsonify({'furniture': furniture_list})
        
    except Exception as e:
        log_project(f"获取家具列表错误: {str(e)}")
        return jsonify({'error': '获取家具列表失败'}), 500

@app.route('/furniture/<filename>')
def serve_furniture(filename):
    """提供家具图片"""
    return send_from_directory(app.config['FURNITURE_FOLDER'], filename)

@app.route('/user/<filename>')
def serve_user_image(filename):
    """提供用户上传的图片"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/output/<filename>')
def serve_output_image(filename):
    """提供生成的图片"""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

@app.route('/masks/<filename>')
def serve_mask_image(filename):
    """提供mask图片"""
    return send_from_directory(app.config['MASK_FOLDER'], filename)

@app.route('/save_mask', methods=['POST'])
def save_mask():
    """保存用户绘制的mask图片"""
    try:
        data = request.get_json()
        
        original_image = data.get('original_image', '')
        mask_data = data.get('mask_data', '')
        
        if not original_image or not mask_data:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 保存mask图片
        mask_filename, mask_filepath = save_mask_image(original_image, mask_data)
        
        return jsonify({
            'success': True,
            'mask_filename': mask_filename,
            'mask_path': f'/masks/{mask_filename}',
            'message': 'Mask图片保存成功'
        })
        
    except Exception as e:
        log_project(f"保存mask图片错误: {str(e)}")
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

@app.route('/api/inpaint', methods=['POST'])
def inpaint_image():
    """图像修复接口：使用通义千问qwen-image-edit-plus模型擦除家具"""
    try:
        if not DASHSCOPE_AVAILABLE:
            return jsonify({'error': 'DashScope SDK未安装，图像修复功能不可用'}), 500
        
        # 检查是否有文件上传
        if 'original_image' not in request.files or 'mask_image' not in request.files:
            return jsonify({'error': '缺少必要参数：需要上传original_image和mask_image'}), 400
        
        original_file = request.files['original_image']
        mask_file = request.files['mask_image']
        
        if original_file.filename == '' or mask_file.filename == '':
            return jsonify({'error': '文件不能为空'}), 400
        
        # 保存上传的文件
        upload_folder = app.config['UPLOAD_FOLDER']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        original_filename = secure_filename(original_file.filename)
        original_unique = f"{uuid.uuid4()}_inpaint_original_{timestamp}_{original_filename}"
        original_path = os.path.join(upload_folder, original_unique)
        original_file.save(original_path)
        
        mask_filename = secure_filename(mask_file.filename)
        mask_unique = f"{uuid.uuid4()}_inpaint_mask_{timestamp}_{mask_filename}"
        mask_path = os.path.join(upload_folder, mask_unique)
        mask_file.save(mask_path)
        
        log_project(f"开始图像修复 - 原图: {original_unique}, 蒙版: {mask_unique}")
        
        # 调用通义千问图像修复API
        result = call_qwen_inpaint(original_path, mask_path)
        
        if result['success']:
            # 下载并保存生成的图片
            generated_images = result['images']
            saved_images = []
            
            for i, image_url in enumerate(generated_images):
                try:
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        output_filename = f"inpaint_{timestamp}_{i+1}.jpg"
                        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        
                        with open(output_filepath, 'wb') as f:
                            f.write(img_response.content)
                        
                        saved_images.append({
                            'filename': output_filename,
                            'path': f'/output/{output_filename}',
                            'url': image_url
                        })
                        
                        log_project(f"保存修复图片: {output_filename}")
                    
                except Exception as e:
                    log_project(f"下载修复图片失败: {str(e)}")
            
            # 清理临时文件
            try:
                if os.path.exists(original_path):
                    os.remove(original_path)
                if os.path.exists(mask_path):
                    os.remove(mask_path)
            except Exception as e:
                log_project(f"清理临时文件失败: {str(e)}")
            
            return jsonify({
                'success': True,
                'generated_images': saved_images,
                'message': f'成功生成 {len(saved_images)} 张修复图片'
            })
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        error_msg = f"图像修复错误: {str(e)}"
        log_project(error_msg)
        import traceback
        log_project(f"异常堆栈:\n{traceback.format_exc()}")
        return jsonify({'error': error_msg}), 500

def call_qwen_inpaint(original_image_path, mask_image_path):
    """调用通义千问qwen-image-edit-plus模型进行图像修复"""
    if not DASHSCOPE_AVAILABLE:
        raise Exception("DashScope SDK未安装")
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise Exception("未配置DASHSCOPE_API_KEY环境变量")
    
    try:
        # 压缩图片（如果需要）
        original_compressed_path, original_compressed = compress_image_for_api(original_image_path, max_dimension=1024)
        mask_compressed_path, mask_compressed = compress_image_for_api(mask_image_path, max_dimension=1024)
        
        temp_files = []
        if original_compressed:
            temp_files.append(original_compressed_path)
        if mask_compressed:
            temp_files.append(mask_compressed_path)
        
        # 编码原始图片为Base64
        original_base64 = encode_file_to_base64(original_compressed_path if original_compressed else original_image_path)
        
        log_project(f"开始调用通义千问图像修复API")
        
        # 处理蒙版图片，确保是纯黑白格式
        try:
            with Image.open(mask_compressed_path if mask_compressed else mask_image_path) as mask_img:
                # 转换为RGB模式（去除透明度）
                if mask_img.mode != 'RGB':
                    mask_img = mask_img.convert('RGB')
                
                # 转换为灰度图
                mask_gray = mask_img.convert('L')
                
                # 二值化：将非黑色区域（要擦除的区域）设为白色(255)，黑色区域(保留)保持为0
                # 使用PIL的像素操作，避免依赖numpy
                pixels = list(mask_gray.getdata())
                binary_pixels = []
                white_count = 0
                black_count = 0
                
                for pixel in pixels:
                    # 阈值处理：大于10的像素设为255（白色），其余为0（黑色）
                    if pixel > 10:
                        binary_pixels.append(255)  # 白色 = 要擦除
                        white_count += 1
                    else:
                        binary_pixels.append(0)   # 黑色 = 保留
                        black_count += 1
                
                # 创建新的纯黑白蒙版图片
                binary_mask_img = Image.new('L', mask_gray.size)
                binary_mask_img.putdata(binary_pixels)
                
                # 转换为RGB（因为API可能需要RGB格式）
                binary_mask_rgb = binary_mask_img.convert('RGB')
                
                # 保存处理后的蒙版（临时文件）
                processed_mask_path = mask_image_path + '.processed.png'
                binary_mask_rgb.save(processed_mask_path, 'PNG')
                temp_files.append(processed_mask_path)
                
                # 使用处理后的蒙版
                mask_path_to_encode = processed_mask_path
                
                log_project(f"蒙版已处理为纯黑白格式，白色区域={white_count}像素（要擦除），黑色区域={black_count}像素（保留）")
        except Exception as e:
            log_project(f"处理蒙版图片失败，使用原始蒙版: {str(e)}")
            mask_path_to_encode = mask_compressed_path if mask_compressed else mask_image_path
        
        # 编码处理后的蒙版
        mask_base64 = encode_file_to_base64(mask_path_to_encode)
        
        # 构造prompt - 明确说明要移除涂抹区域的家具，恢复为空的房间背景
        prompt_text = "Remove the furniture in the white marked areas, restore the empty room background naturally. Keep the room structure unchanged, only remove the furniture objects. Generate a clean, empty living room space with the original room style and lighting."
        
        # 调用API
        response = MultiModalConversation.call(
            api_key=api_key,
            model="qwen-image-edit-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": original_base64},
                        {"image": mask_base64},
                        {"text": prompt_text}
                    ]
                }
            ],
            stream=False,
            n=1,  # 生成1张图片
            watermark=False,
            negative_prompt="low quality, blurry, distorted, unrealistic, furniture visible",
            prompt_extend=True
        )
        
        # 处理响应
        if response.status_code == 200:
            generated_images = []
            if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                for choice in response.output.choices:
                    if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                        for content_item in choice.message.content:
                            if isinstance(content_item, dict) and 'image' in content_item:
                                generated_images.append(content_item['image'])
            
            log_project(f"通义千问API调用成功，生成{len(generated_images)}张图片")
            
            return {
                'success': True,
                'images': generated_images
            }
        else:
            error_msg = f"通义千问API调用失败: status_code={response.status_code}"
            if hasattr(response, 'code'):
                error_msg += f", code={response.code}"
            if hasattr(response, 'message'):
                error_msg += f", message={response.message}"
            
            log_project(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
            
    except Exception as e:
        error_msg = f"通义千问图像修复异常: {str(e)}"
        log_project(error_msg)
        import traceback
        log_project(f"异常堆栈:\n{traceback.format_exc()}")
        return {
            'success': False,
            'error': error_msg
        }
    finally:
        # 清理临时压缩文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    log_project(f"已清理临时文件: {temp_file}")
            except Exception as e:
                log_project(f"清理临时文件失败 {temp_file}: {str(e)}")

@app.route('/generate_v1', methods=['POST'])
def generate_decoration_v1():
    """v1.0版本：调用豆包图像融合API生成家装效果图"""
    try:
        data = request.get_json()
        
        # 获取参数
        original_image = data.get('original_image', '')
        selected_furniture = data.get('selected_furniture', '')
        mask_filename = data.get('mask_filename', '')
        
        if not all([original_image, selected_furniture, mask_filename]):
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 构建文件路径
        mask_path = os.path.join(app.config['MASK_FOLDER'], mask_filename)
        furniture_path = os.path.join(app.config['FURNITURE_FOLDER'], selected_furniture)
        
        # 检查文件是否存在
        if not os.path.exists(mask_path):
            return jsonify({'error': f'Mask图片不存在: {mask_filename}'}), 400
        
        if not os.path.exists(furniture_path):
            return jsonify({'error': f'家具图片不存在: {selected_furniture}'}), 400
        
        # 构造prompt
        prompt_text = f"""在图一客厅中我涂成蓝色的部分放置图二中选择的沙发，要求自然的融入到图一中，
        尤其注意:客厅图一我没有涂蓝色的部分不要做任何变动。
        保持沙发的原始外观特征，调整光影和透视以匹配客厅环境。
        生成的图片中我用于标记沙发放置位置的蓝色不要再出现"""
        
        log_project(f"开始生成装修效果图 - 原图: {original_image}, 家具: {selected_furniture}, Mask: {mask_filename}")
        log_project(f"Mask图片路径: {mask_path}")
        log_project(f"家具图片路径: {furniture_path}")
        
        # 验证mask图片是否存在且可读
        if os.path.exists(mask_path):
            try:
                with Image.open(mask_path) as test_img:
                    log_project(f"Mask图片验证成功 - 尺寸: {test_img.size}, 模式: {test_img.mode}")
            except Exception as e:
                log_project(f"Mask图片验证失败: {str(e)}")
        else:
            log_project(f"错误: Mask图片不存在: {mask_path}")
        
        # 调用豆包图像融合API
        result = call_doubao_image_fusion(mask_path, furniture_path, prompt_text)
        
        if result['success']:
            # 下载并保存生成的图片
            generated_images = result['images']
            saved_images = []
            
            for i, image_url in enumerate(generated_images):
                try:
                    import requests
                    img_response = requests.get(image_url)
                    if img_response.status_code == 200:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_filename = f"generated_v1_{timestamp}_{i+1}.jpg"
                        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        
                        with open(output_filepath, 'wb') as f:
                            f.write(img_response.content)
                        
                        saved_images.append({
                            'filename': output_filename,
                            'path': f'/output/{output_filename}',
                            'url': image_url
                        })
                        
                        log_project(f"保存生成图片: {output_filename}")
                    
                except Exception as e:
                    log_project(f"下载生成图片失败: {str(e)}")
            
            # 记录生成日志
            generation_log = {
                "timestamp": datetime.now().isoformat(),
                "version": "v1.0",
                "input": {
                    "original_image": original_image,
                    "selected_furniture": selected_furniture,
                    "mask_filename": mask_filename
                },
                "prompt": prompt_text,
                "result": {
                    "success": result['success'],
                    "images_count": len(result['images']),
                    "generated_urls": result['images']
                },
                "saved_images": saved_images
            }
            
            log_file = os.path.join(BASE_DIR, 'project_log', f"generation_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(generation_log, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'generated_images': saved_images,
                'message': f'成功生成 {len(saved_images)} 张装修效果图'
            })
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        error_msg = f"生成装修效果图错误: {str(e)}"
        log_project(error_msg)
        return jsonify({'error': error_msg}), 500

def init_app_resources():
    """初始化应用资源（预加载缓存，避免首次请求延迟）"""
    try:
        # 预加载家具元数据缓存
        load_furniture_metadata()
        log_project("应用资源初始化完成：家具元数据缓存已加载")
    except Exception as e:
        log_project(f"应用资源初始化失败: {str(e)}")

# 在模块加载时初始化资源（适用于Gunicorn等生产环境）
try:
    init_app_resources()
except Exception as e:
    print(f"警告: 应用资源初始化失败: {str(e)}")

if __name__ == '__main__':
    # 目录已在模块级别创建，这里只是确认（用于直接运行时的日志输出）
    print("目录检查完成（已在模块级别创建）")
    
    # 检查豆包SDK可用性
    if DOUBAO_AVAILABLE:
        print("豆包SDK可用，图像生成功能正常")
        # 预初始化豆包客户端（单例模式）
        try:
            get_doubao_client()
            print("豆包客户端初始化成功")
        except Exception as e:
            print(f"豆包客户端初始化失败: {str(e)}")
    else:
        print("豆包SDK不可用，请安装: pip install 'volcengine-python-sdk[ark]'")
    
    print(f"家具文件夹路径: {app.config['FURNITURE_FOLDER']}")
    if os.path.exists(app.config['FURNITURE_FOLDER']):
        files = os.listdir(app.config['FURNITURE_FOLDER'])
        print(f"家具文件夹中的文件: {files}")
    else:
        print("警告: 家具文件夹不存在!")
    
    # 生产环境配置：支持 Render 等云平台的 PORT 环境变量
    port = int(os.getenv('PORT', 5423))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 如果是生产环境，强制关闭debug模式
    if os.getenv('FLASK_ENV') == 'production':
        debug = False
    
    print(f"启动AI装修应用 v1.0 on port {port}, debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port)