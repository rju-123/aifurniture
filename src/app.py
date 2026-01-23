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

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_project(message):
    """记录项目日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(BASE_DIR, 'project_log', 'project.log')
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")

def encode_file_to_base64(file_path):
    """将本地图片文件转换为 Base64 Data URL"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"图片文件不存在: {file_path}")
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("不支持或无法识别的图像格式")
    
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
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
        
        # 使用PIL直接从内存分析mask数据
        try:
            with Image.open(io.BytesIO(mask_image_data)) as temp_mask:
                log_project(f"内存中mask图片: 尺寸={temp_mask.size}, 模式={temp_mask.mode}, 格式={temp_mask.format}")
                
                # 转换为RGBA进行分析
                if temp_mask.mode != 'RGBA':
                    temp_mask = temp_mask.convert('RGBA')
                
                # 分析前100个非透明像素的alpha值
                # 使用新的 get_flattened_data() 方法（Pillow 10.0+）
                try:
                    pixels = list(temp_mask.get_flattened_data())
                except AttributeError:
                    # 兼容旧版本 Pillow
                    pixels = list(temp_mask.getdata())
                non_transparent_pixels = [(i, pixel) for i, pixel in enumerate(pixels) if pixel[3] > 0]
                
                log_project(f"内存分析: 总像素={len(pixels)}, 非透明像素={len(non_transparent_pixels)}")
                
                if non_transparent_pixels:
                    # 分析前10个非透明像素
                    sample_pixels = non_transparent_pixels[:10]
                    alpha_values = [pixel[1][3] for pixel in sample_pixels]
                    
                    log_project(f"样本像素alpha值: {alpha_values}")
                    
                    # 统计所有alpha值
                    all_alphas = [pixel[3] for pixel in pixels if pixel[3] > 0]
                    unique_alphas = list(set(all_alphas))
                    
                    if all_alphas:
                        most_common_alpha = max(set(all_alphas), key=all_alphas.count)
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
        original_image_path = os.path.join(app.config['UPLOAD_FOLDER'], original_image_filename)
        
        if os.path.exists(original_image_path):
            # 打开原始图片和mask图片
            with Image.open(original_image_path) as original_img:
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
                    
                    # 分析mask的透明度信息
                    # 使用新的 get_flattened_data() 方法（Pillow 10.0+）
                    try:
                        mask_pixels = list(mask_img.get_flattened_data())
                    except AttributeError:
                        # 兼容旧版本 Pillow
                        mask_pixels = list(mask_img.getdata())
                    alpha_values = [pixel[3] for pixel in mask_pixels if pixel[3] > 0]  # 非透明像素的alpha值
                    avg_alpha = sum(alpha_values) / len(alpha_values) if alpha_values else 0
                    transparency_percentage = round((255 - avg_alpha) / 255 * 100, 2) if avg_alpha > 0 else 100
                    
                    log_project(f"Mask透明度分析: 平均Alpha={avg_alpha:.1f}, 透明度={transparency_percentage}%")
                    
                    # 创建叠加图片 - 手动处理透明度混合
                    composite_img = original_img.copy()
                    
                    # 获取像素数据进行手动混合
                    # 使用新的 get_flattened_data() 方法（Pillow 10.0+）
                    try:
                        original_pixels = list(original_img.get_flattened_data())
                        mask_pixels = list(mask_img.get_flattened_data())
                    except AttributeError:
                        # 兼容旧版本 Pillow
                        original_pixels = list(original_img.getdata())
                        mask_pixels = list(mask_img.getdata())
                    
                    # 手动混合像素，正确处理用户设置的透明度
                    blended_pixels = []
                    processed_count = 0
                    
                    for orig_pixel, mask_pixel in zip(original_pixels, mask_pixels):
                        if mask_pixel[3] == 0:  # mask像素完全透明，保持原始像素
                            blended_pixels.append(orig_pixel)
                        else:  # mask像素有颜色，这里需要正确处理透明度
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
                            
                            blended_pixels.append((blended_r, blended_g, blended_b, blended_a))
                    
                    log_project(f"透明度处理统计: 处理了{processed_count}个mask像素")
                    
                    if alpha_values:
                        most_common_alpha = max(set(alpha_values), key=alpha_values.count)
                        actual_transparency = round((255 - most_common_alpha) / 255 * 100, 1)
                        log_project(f"检测到的用户透明度设置: {actual_transparency}% (alpha={most_common_alpha})")
                    
                    # 创建新图片
                    composite_img.putdata(blended_pixels)
                    
                    # 保存叠加图片
                    composite_filename = f"{base_name}_composite_mask_{timestamp}.png"
                    composite_filepath = os.path.join(app.config['MASK_FOLDER'], composite_filename)
                    composite_img.save(composite_filepath, 'PNG')
                    
                    log_project(f"生成叠加mask图片: {composite_filename}, 保持透明度: {transparency_percentage}%")
        else:
            log_project(f"警告: 原始图片不存在: {original_image_path}")
            composite_filename = pure_mask_filename
            composite_filepath = pure_mask_filepath
        
        log_project(f"保存叠加mask图片: {composite_filename}")
        
        # 返回叠加图片的信息（这是要传给API的）
        return composite_filename, composite_filepath
        
    except Exception as e:
        log_project(f"保存mask图片失败: {str(e)}")
        raise e

def call_doubao_image_fusion(mask_image_path, furniture_image_path, prompt_text):
    """调用豆包图像融合API"""
    if not DOUBAO_AVAILABLE:
        raise Exception("豆包SDK未安装")
    
    # 配置API
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        raise Exception("未配置ARK_API_KEY环境变量")
    
    # 初始化客户端
    client = Ark(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key
    )
    
    try:
        # 编码图片为Base64
        mask_base64 = encode_file_to_base64(mask_image_path)
        furniture_base64 = encode_file_to_base64(furniture_image_path)
        
        log_project(f"开始调用豆包API - mask: {mask_image_path}, furniture: {furniture_image_path}")
        
        # 调用豆包图片生成API
        response = client.images.generate(
            model="doubao-seedream-4-5-251128",  # 豆包模型ID
            prompt=prompt_text,
            image=[mask_base64, furniture_base64],  # 本地图片Base64列表
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
        return {
            'success': False,
            'error': error_msg
        }

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
            # 生成唯一文件名
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # 保存文件
            file.save(filepath)
            
            # 记录日志
            log_project(f"用户上传客厅图片: {unique_filename}")
            
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

def load_furniture_metadata():
    """加载家具元数据文件"""
    metadata_path = os.path.join(app.config['FURNITURE_FOLDER'], 'furniture_metadata.json')
    
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                return metadata.get('furniture', [])
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

if __name__ == '__main__':
    # 确保必要的目录存在
    for folder in [app.config['UPLOAD_FOLDER'], app.config['FURNITURE_FOLDER'], 
                   app.config['OUTPUT_FOLDER'], app.config['MASK_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
        print(f"确保目录存在: {folder}")
    
    # 确保日志目录存在
    log_dirs = [
        os.path.join(BASE_DIR, 'project_log')
    ]
    for log_dir in log_dirs:
        os.makedirs(log_dir, exist_ok=True)
        print(f"确保日志目录存在: {log_dir}")
    
    # 检查豆包SDK可用性
    if DOUBAO_AVAILABLE:
        print("豆包SDK可用，图像生成功能正常")
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