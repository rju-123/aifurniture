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

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 配置文件夹路径
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'data', 'user')
app.config['FURNITURE_FOLDER'] = os.path.join(BASE_DIR, 'data', 'furniture')
app.config['OUTPUT_FOLDER'] = os.path.join(BASE_DIR, 'data', 'output')
app.config['MASK_FOLDER'] = os.path.join(BASE_DIR, 'data', 'masks')
app.config['DEBUG_FOLDER'] = os.path.join(BASE_DIR, 'debug')  # 新增：调试数据存储
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_project(message):
    """记录项目日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(BASE_DIR, 'project_log', 'project_debug.log')
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [DEBUG] {message}\n")
    
    # 同时打印到控制台
    print(f"[{timestamp}] [DEBUG] {message}")

def debug_log(data, filename_prefix="debug"):
    """记录调试数据到JSON文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 精确到毫秒
    debug_filename = f"{filename_prefix}_{timestamp}.json"
    debug_filepath = os.path.join(app.config['DEBUG_FOLDER'], debug_filename)
    
    with open(debug_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    log_project(f"调试数据已保存: {debug_filename}")
    return debug_filename

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

def analyze_mask_image(mask_filepath):
    """分析mask图片的详细信息"""
    try:
        with Image.open(mask_filepath) as img:
            # 基本信息
            width, height = img.size
            mode = img.mode
            format_info = img.format
            
            # 转换为RGBA以便分析
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 统计像素信息
            pixels = list(img.getdata())
            total_pixels = len(pixels)
            
            # 分析颜色分布
            color_stats = {}
            blue_pixels = 0
            transparent_pixels = 0
            background_pixels = 0  # 非蓝色非透明的像素（背景内容）
            alpha_distribution = {}  # 统计alpha值分布
            blue_alpha_values = []  # 专门记录蓝色像素的alpha值
            
            for pixel in pixels:
                r, g, b, a = pixel
                
                # 统计alpha值分布
                alpha_distribution[a] = alpha_distribution.get(a, 0) + 1
                
                # 统计透明像素
                if a == 0:
                    transparent_pixels += 1
                    continue
                
                # 统计蓝色像素（用于mask标记）
                if b > r and b > g and b > 100:  # 蓝色占主导且足够明显
                    blue_pixels += 1
                    blue_alpha_values.append(a)  # 记录蓝色像素的alpha值
                else:
                    # 非蓝色的不透明像素，认为是背景内容
                    background_pixels += 1
                
                # 颜色统计
                color_key = f"rgba({r},{g},{b},{a})"
                color_stats[color_key] = color_stats.get(color_key, 0) + 1
            
            # 获取主要颜色（排除透明）
            non_transparent_colors = {k: v for k, v in color_stats.items() if not k.startswith('rgba(0,0,0,0)')}
            top_colors = sorted(non_transparent_colors.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # 判断图片类型
            is_composite = background_pixels > 0  # 有背景内容说明是叠加图片
            is_pure_mask = background_pixels == 0 and blue_pixels > 0  # 只有蓝色和透明说明是纯mask
            
            analysis = {
                "basic_info": {
                    "width": width,
                    "height": height,
                    "mode": mode,
                    "format": format_info,
                    "total_pixels": total_pixels
                },
                "pixel_analysis": {
                    "transparent_pixels": transparent_pixels,
                    "transparent_percentage": round(transparent_pixels / total_pixels * 100, 2),
                    "blue_pixels": blue_pixels,
                    "blue_percentage": round(blue_pixels / total_pixels * 100, 2),
                    "background_pixels": background_pixels,
                    "background_percentage": round(background_pixels / total_pixels * 100, 2),
                    "opaque_pixels": total_pixels - transparent_pixels,
                    "opaque_percentage": round((total_pixels - transparent_pixels) / total_pixels * 100, 2)
                },
                "alpha_analysis": {
                    "alpha_distribution": alpha_distribution,
                    "blue_alpha_values": blue_alpha_values[:10],  # 只记录前10个样本
                    "blue_alpha_unique": list(set(blue_alpha_values)) if blue_alpha_values else [],
                    "blue_alpha_most_common": max(set(blue_alpha_values), key=blue_alpha_values.count) if blue_alpha_values else 0,
                    "detected_transparency": round((255 - max(set(blue_alpha_values), key=blue_alpha_values.count)) / 255 * 100, 1) if blue_alpha_values else 0
                },
                "image_type": {
                    "is_composite": is_composite,
                    "is_pure_mask": is_pure_mask,
                    "description": "叠加图片(原图+蓝色涂抹)" if is_composite else "纯mask图片(仅蓝色区域)" if is_pure_mask else "其他类型"
                },
                "color_distribution": {
                    "unique_colors": len(color_stats),
                    "top_colors": top_colors
                }
            }
            
            return analysis
            
    except Exception as e:
        return {"error": f"分析mask图片失败: {str(e)}"}

def save_mask_image(original_image_filename, mask_data):
    """保存用户绘制的mask图片并进行详细分析 - 生成原始图片+蓝色涂抹的叠加图片"""
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
        mask_memory_analysis = {}
        try:
            with Image.open(io.BytesIO(mask_image_data)) as temp_mask:
                log_project(f"内存中mask图片: 尺寸={temp_mask.size}, 模式={temp_mask.mode}, 格式={temp_mask.format}")
                
                # 转换为RGBA进行分析
                if temp_mask.mode != 'RGBA':
                    temp_mask = temp_mask.convert('RGBA')
                
                # 分析前100个非透明像素的alpha值
                pixels = list(temp_mask.getdata())
                non_transparent_pixels = [(i, pixel) for i, pixel in enumerate(pixels) if pixel[3] > 0]
                
                log_project(f"内存分析: 总像素={len(pixels)}, 非透明像素={len(non_transparent_pixels)}")
                
                if non_transparent_pixels:
                    # 分析前10个非透明像素
                    sample_pixels = non_transparent_pixels[:10]
                    alpha_values = [pixel[1][3] for pixel in sample_pixels]
                    
                    log_project(f"样本像素alpha值: {alpha_values}")
                    log_project(f"样本像素详情: {[(f'位置{p[0]}', p[1]) for p in sample_pixels[:3]]}")
                    
                    # 统计所有alpha值
                    all_alphas = [pixel[3] for pixel in pixels if pixel[3] > 0]
                    unique_alphas = list(set(all_alphas))
                    
                    mask_memory_analysis = {
                        "total_pixels": len(pixels),
                        "non_transparent_count": len(non_transparent_pixels),
                        "unique_alpha_values": unique_alphas,
                        "sample_alphas": alpha_values,
                        "most_common_alpha": max(set(all_alphas), key=all_alphas.count) if all_alphas else 0
                    }
                    
                    if mask_memory_analysis["most_common_alpha"] > 0:
                        detected_transparency = round((255 - mask_memory_analysis["most_common_alpha"]) / 255 * 100, 1)
                        log_project(f"内存分析检测到透明度: {detected_transparency}% (alpha={mask_memory_analysis['most_common_alpha']})")
                else:
                    log_project("警告: 内存中的mask图片没有找到非透明像素!")
                    
        except Exception as e:
            log_project(f"内存mask分析失败: {str(e)}")
            mask_memory_analysis = {"error": str(e)}
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(original_image_filename)[0]
        
        # 1. 先保存原始的mask图片（纯蓝色区域）用于分析
        pure_mask_filename = f"{base_name}_pure_mask_{timestamp}.png"
        pure_mask_filepath = os.path.join(app.config['MASK_FOLDER'], pure_mask_filename)
        
        with open(pure_mask_filepath, 'wb') as f:
            f.write(mask_image_data)
        
        log_project(f"保存纯mask文件: {pure_mask_filename}")
        
        # 分析保存后的纯mask图片
        pure_mask_analysis = analyze_mask_image(pure_mask_filepath)
        
        # 比较内存分析和文件分析的结果
        if "most_common_alpha" in mask_memory_analysis and "pixel_analysis" in pure_mask_analysis:
            memory_alpha = mask_memory_analysis["most_common_alpha"]
            # 从pure_mask_analysis中提取alpha信息
            file_pixels = pure_mask_analysis.get("pixel_analysis", {})
            log_project(f"透明度对比: 内存alpha={memory_alpha}, 文件分析={file_pixels}")
        
        # 将内存分析结果添加到调试数据
        pure_mask_analysis["memory_analysis"] = mask_memory_analysis
        
        # 2. 生成叠加图片：原始图片 + 蓝色涂抹
        original_image_path = os.path.join(app.config['UPLOAD_FOLDER'], original_image_filename)
        
        # 初始化调试数据结构
        debug_data = {
            "action": "save_mask_image_composite",
            "timestamp": datetime.now().isoformat(),
            "input": {
                "original_image_filename": original_image_filename,
                "original_image_path": original_image_path,
                "original_image_exists": os.path.exists(original_image_path),
                "mask_data_length": len(mask_data),
                "mask_data_prefix": mask_data[:100] if len(mask_data) > 100 else mask_data,
                "base64_data_length": len(base64_data),
                "decoded_image_size": len(mask_image_data)
            }
        }
        
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
                    mask_pixels = list(mask_img.getdata())
                    alpha_values = [pixel[3] for pixel in mask_pixels if pixel[3] > 0]  # 非透明像素的alpha值
                    avg_alpha = sum(alpha_values) / len(alpha_values) if alpha_values else 0
                    transparency_percentage = round((255 - avg_alpha) / 255 * 100, 2) if avg_alpha > 0 else 100
                    
                    log_project(f"Mask透明度分析: 平均Alpha={avg_alpha:.1f}, 透明度={transparency_percentage}%")
                    
                    # 创建叠加图片 - 手动处理透明度混合
                    composite_img = original_img.copy()
                    
                    # 获取像素数据进行手动混合
                    original_pixels = list(original_img.getdata())
                    mask_pixels = list(mask_img.getdata())
                    
                    # 手动混合像素，正确处理用户设置的透明度
                    blended_pixels = []
                    
                    # 记录透明度处理的详细信息
                    transparency_debug = {
                        "total_pixels": len(original_pixels),
                        "mask_pixels_processed": 0,
                        "transparent_pixels": 0,
                        "alpha_values_found": [],
                        "sample_pixels": []
                    }
                    
                    for i, (orig_pixel, mask_pixel) in enumerate(zip(original_pixels, mask_pixels)):
                        if mask_pixel[3] == 0:  # mask像素完全透明，保持原始像素
                            blended_pixels.append(orig_pixel)
                            transparency_debug["transparent_pixels"] += 1
                        else:  # mask像素有颜色，这里需要正确处理透明度
                            transparency_debug["mask_pixels_processed"] += 1
                            
                            # 获取mask的alpha值（这是用户设置的透明度）
                            user_alpha = mask_pixel[3]  # 用户设置的alpha值
                            user_alpha_ratio = user_alpha / 255.0  # 转换为0-1的比例
                            
                            # 记录alpha值用于调试
                            transparency_debug["alpha_values_found"].append(user_alpha)
                            
                            # Alpha混合公式: result = mask * user_alpha + original * (1 - user_alpha)
                            blended_r = int(mask_pixel[0] * user_alpha_ratio + orig_pixel[0] * (1 - user_alpha_ratio))
                            blended_g = int(mask_pixel[1] * user_alpha_ratio + orig_pixel[1] * (1 - user_alpha_ratio))
                            blended_b = int(mask_pixel[2] * user_alpha_ratio + orig_pixel[2] * (1 - user_alpha_ratio))
                            
                            # 关键修复：最终alpha值应该体现叠加效果
                            # 如果原始背景是不透明的，叠加后仍应该是不透明的
                            # 但颜色已经混合了用户的透明度设置
                            blended_a = orig_pixel[3]  # 保持原始背景的不透明度
                            
                            # 记录样本像素用于调试
                            if len(transparency_debug["sample_pixels"]) < 5:
                                transparency_debug["sample_pixels"].append({
                                    "index": i,
                                    "original": orig_pixel,
                                    "mask": mask_pixel,
                                    "user_alpha": user_alpha,
                                    "user_alpha_ratio": user_alpha_ratio,
                                    "blended": (blended_r, blended_g, blended_b, blended_a)
                                })
                            
                            blended_pixels.append((blended_r, blended_g, blended_b, blended_a))
                    
                    # 记录透明度处理的统计信息
                    unique_alphas = list(set(transparency_debug["alpha_values_found"]))
                    transparency_debug["unique_alpha_values"] = unique_alphas
                    transparency_debug["most_common_alpha"] = max(set(transparency_debug["alpha_values_found"]), key=transparency_debug["alpha_values_found"].count) if transparency_debug["alpha_values_found"] else 0
                    
                    log_project(f"透明度处理统计: 处理了{transparency_debug['mask_pixels_processed']}个mask像素, 发现的alpha值: {unique_alphas}")
                    
                    # 如果用户设置了30%透明度，mask的alpha应该是178 (70%不透明)
                    expected_alpha_30_percent = int(255 * 0.7)  # 178
                    if transparency_debug["most_common_alpha"] > 0:
                        actual_transparency = round((255 - transparency_debug["most_common_alpha"]) / 255 * 100, 1)
                        log_project(f"检测到的用户透明度设置: {actual_transparency}% (alpha={transparency_debug['most_common_alpha']})")
                    
                    # 保存透明度调试信息
                    debug_data["transparency_processing"] = transparency_debug
                    
                    # 创建新图片
                    composite_img.putdata(blended_pixels)
                    
                    # 保存叠加图片
                    composite_filename = f"{base_name}_composite_mask_{timestamp}.png"
                    composite_filepath = os.path.join(app.config['MASK_FOLDER'], composite_filename)
                    composite_img.save(composite_filepath, 'PNG')
                    
                    # 分析叠加图片
                    composite_analysis = analyze_mask_image(composite_filepath)
                    
                    log_project(f"生成叠加mask图片: {composite_filename}, 保持透明度: {transparency_percentage}%")
        else:
            log_project(f"警告: 原始图片不存在: {original_image_path}")
            composite_filename = pure_mask_filename
            composite_filepath = pure_mask_filepath
            composite_analysis = {"error": "原始图片不存在，使用纯mask"}
        
        # 更新调试数据的其他字段
        debug_data.update({
            "transparency_analysis": {
                "avg_alpha": avg_alpha if 'avg_alpha' in locals() else 0,
                "transparency_percentage": transparency_percentage if 'transparency_percentage' in locals() else 0,
                "alpha_values_count": len(alpha_values) if 'alpha_values' in locals() else 0
            },
            "output": {
                "pure_mask_filename": pure_mask_filename,
                "pure_mask_filepath": pure_mask_filepath,
                "pure_mask_exists": os.path.exists(pure_mask_filepath),
                "pure_mask_size": os.path.getsize(pure_mask_filepath) if os.path.exists(pure_mask_filepath) else 0,
                "composite_filename": composite_filename,
                "composite_filepath": composite_filepath,
                "composite_exists": os.path.exists(composite_filepath),
                "composite_size": os.path.getsize(composite_filepath) if os.path.exists(composite_filepath) else 0
            },
            "analysis": {
                "pure_mask_analysis": pure_mask_analysis,
                "composite_analysis": composite_analysis
            }
        })
        
        debug_log(debug_data, "mask_save_composite")
        
        blue_percentage = pure_mask_analysis.get('pixel_analysis', {}).get('blue_percentage', 0)
        log_project(f"保存叠加mask图片: {composite_filename}, 蓝色像素占比: {blue_percentage}%")
        
        # 返回叠加图片的信息（这是要传给API的）
        return composite_filename, composite_filepath
        
    except Exception as e:
        error_data = {
            "action": "save_mask_image_error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "input": {
                "original_image_filename": original_image_filename,
                "mask_data_length": len(mask_data) if mask_data else 0
            }
        }
        debug_log(error_data, "mask_save_error")
        log_project(f"保存mask图片失败: {str(e)}")
        raise e

def mock_qwen_image_fusion(mask_image_path, furniture_image_path, prompt_text):
    """模拟千问图像融合API调用 - 不进行真实调用但记录所有输入数据"""
    try:
        # 分析输入文件
        mask_exists = os.path.exists(mask_image_path)
        furniture_exists = os.path.exists(furniture_image_path)
        
        mask_size = os.path.getsize(mask_image_path) if mask_exists else 0
        furniture_size = os.path.getsize(furniture_image_path) if furniture_exists else 0
        
        # 分析mask图片
        mask_analysis = analyze_mask_image(mask_image_path) if mask_exists else {"error": "文件不存在"}
        
        # 尝试编码图片为Base64（用于验证）
        mask_base64 = None
        furniture_base64 = None
        encoding_errors = []
        
        try:
            if mask_exists:
                mask_base64 = encode_file_to_base64(mask_image_path)
                log_project(f"Mask图片Base64编码成功，长度: {len(mask_base64)}")
        except Exception as e:
            encoding_errors.append(f"Mask编码失败: {str(e)}")
        
        try:
            if furniture_exists:
                furniture_base64 = encode_file_to_base64(furniture_image_path)
                log_project(f"家具图片Base64编码成功，长度: {len(furniture_base64)}")
        except Exception as e:
            encoding_errors.append(f"家具编码失败: {str(e)}")
        
        # 构造模拟的API输入数据
        api_input = {
            "model": "qwen-image-edit-plus",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": mask_base64[:100] + "..." if mask_base64 else None},  # 只记录前100字符
                        {"image": furniture_base64[:100] + "..." if furniture_base64 else None},
                        {"text": prompt_text}
                    ]
                }
            ],
            "stream": False,
            "n": 1,
            "watermark": False,
            "negative_prompt": "增加图一、图二以外的元素，模糊, 变形, 不真实, 低质量, 不协调",
            "prompt_extend": True,
            "seed": 12345
        }
        
        # 记录完整的调试数据
        debug_data = {
            "action": "mock_qwen_image_fusion",
            "timestamp": datetime.now().isoformat(),
            "input_files": {
                "mask_image_path": mask_image_path,
                "mask_exists": mask_exists,
                "mask_size": mask_size,
                "furniture_image_path": furniture_image_path,
                "furniture_exists": furniture_exists,
                "furniture_size": furniture_size
            },
            "mask_analysis": mask_analysis,
            "prompt_text": prompt_text,
            "api_input": api_input,
            "encoding_status": {
                "mask_base64_length": len(mask_base64) if mask_base64 else 0,
                "furniture_base64_length": len(furniture_base64) if furniture_base64 else 0,
                "encoding_errors": encoding_errors
            },
            "simulation_result": {
                "would_call_api": mask_exists and furniture_exists and not encoding_errors,
                "mock_response": {
                    "status_code": 200,
                    "mock_image_url": f"https://mock-api.example.com/generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                }
            }
        }
        
        debug_filename = debug_log(debug_data, "api_simulation")
        
        # 模拟成功响应
        if mask_exists and furniture_exists and not encoding_errors:
            log_project(f"模拟API调用成功 - 调试数据: {debug_filename}")
            return {
                'success': True,
                'images': [f"https://mock-api.example.com/generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"],
                'debug_file': debug_filename,
                'mock': True
            }
        else:
            error_msg = f"模拟API调用失败 - 文件检查: mask={mask_exists}, furniture={furniture_exists}, 编码错误: {encoding_errors}"
            log_project(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'debug_file': debug_filename,
                'mock': True
            }
            
    except Exception as e:
        error_data = {
            "action": "mock_qwen_image_fusion_error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "input": {
                "mask_image_path": mask_image_path,
                "furniture_image_path": furniture_image_path,
                "prompt_text": prompt_text
            }
        }
        debug_log(error_data, "api_simulation_error")
        return {
            'success': False,
            'error': f"模拟API调用异常: {str(e)}",
            'mock': True
        }

@app.route('/')
def index():
    """主页面 - v1.0重构版本"""
    return render_template('index_v1.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理用户上传的客厅图片"""
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
            
            # 记录调试信息
            debug_data = {
                "action": "upload_file",
                "timestamp": datetime.now().isoformat(),
                "original_filename": filename,
                "unique_filename": unique_filename,
                "filepath": filepath,
                "file_size": os.path.getsize(filepath)
            }
            debug_log(debug_data, "upload")
            
            # 记录日志
            log_project(f"用户上传客厅图片: {unique_filename}")
            
            return jsonify({
                'success': True,
                'filename': unique_filename,
                'message': '客厅图片上传成功'
            })
        else:
            return jsonify({'error': '不支持的文件格式'}), 400
            
    except Exception as e:
        log_project(f"上传文件错误: {str(e)}")
        return jsonify({'error': '上传失败'}), 500

@app.route('/furniture')
def get_furniture_list():
    """获取家具库列表 - v1.0限制为单选"""
    try:
        furniture_folder = app.config['FURNITURE_FOLDER']
        furniture_list = []
        
        if os.path.exists(furniture_folder):
            files = os.listdir(furniture_folder)
            
            for filename in files:
                if allowed_file(filename):
                    furniture_list.append({
                        'name': filename,
                        'path': f'/furniture/{filename}',
                        'display_name': os.path.splitext(filename)[0]  # 显示名称（去掉扩展名）
                    })
        
        log_project(f"返回家具列表，共 {len(furniture_list)} 个家具")
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

@app.route('/debug/<filename>')
def serve_debug_file(filename):
    """提供调试文件"""
    return send_from_directory(app.config['DEBUG_FOLDER'], filename)

@app.route('/save_mask', methods=['POST'])
def save_mask():
    """保存用户绘制的mask图片"""
    try:
        data = request.get_json()
        
        original_image = data.get('original_image', '')
        mask_data = data.get('mask_data', '')
        
        if not original_image or not mask_data:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 保存mask图片（包含详细分析）
        mask_filename, mask_filepath = save_mask_image(original_image, mask_data)
        
        return jsonify({
            'success': True,
            'mask_filename': mask_filename,
            'mask_path': f'/masks/{mask_filename}',
            'message': 'Mask图片保存成功（调试模式）'
        })
        
    except Exception as e:
        log_project(f"保存mask图片错误: {str(e)}")
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

@app.route('/generate_v1', methods=['POST'])
def generate_decoration_v1():
    """v1.0版本：模拟调用千问图像融合API - 调试模式"""
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
        
        log_project(f"开始模拟生成装修效果图 - 原图: {original_image}, 家具: {selected_furniture}, Mask: {mask_filename}")
        
        # 调用模拟的千问图像融合API
        result = mock_qwen_image_fusion(mask_path, furniture_path, prompt_text)
        
        if result['success']:
            # 模拟保存生成的图片
            mock_images = result['images']
            saved_images = []
            
            for i, image_url in enumerate(mock_images):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"mock_generated_v1_{timestamp}_{i+1}.jpg"
                
                saved_images.append({
                    'filename': output_filename,
                    'path': f'/output/{output_filename}',
                    'url': image_url,
                    'mock': True
                })
                
                log_project(f"模拟保存生成图片: {output_filename}")
            
            # 记录完整的生成日志
            generation_log = {
                "timestamp": datetime.now().isoformat(),
                "version": "v1.0_debug",
                "mode": "simulation",
                "input": {
                    "original_image": original_image,
                    "selected_furniture": selected_furniture,
                    "mask_filename": mask_filename,
                    "mask_path": mask_path,
                    "furniture_path": furniture_path
                },
                "prompt": prompt_text,
                "result": result,
                "saved_images": saved_images,
                "debug_file": result.get('debug_file', '')
            }
            
            log_file = os.path.join(BASE_DIR, 'project_log', f"generation_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(generation_log, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'generated_images': saved_images,
                'message': f'模拟生成 {len(saved_images)} 张装修效果图（调试模式）',
                'debug_mode': True,
                'debug_file': result.get('debug_file', ''),
                'generation_log': os.path.basename(log_file)
            })
        else:
            return jsonify({
                'error': result['error'],
                'debug_mode': True,
                'debug_file': result.get('debug_file', '')
            }), 500
            
    except Exception as e:
        error_msg = f"模拟生成装修效果图错误: {str(e)}"
        log_project(error_msg)
        return jsonify({'error': error_msg, 'debug_mode': True}), 500

@app.route('/debug_info')
def debug_info():
    """获取调试信息"""
    debug_folder = app.config['DEBUG_FOLDER']
    debug_files = []
    
    if os.path.exists(debug_folder):
        files = os.listdir(debug_folder)
        for filename in files:
            if filename.endswith('.json'):
                filepath = os.path.join(debug_folder, filename)
                debug_files.append({
                    'filename': filename,
                    'path': f'/debug/{filename}',
                    'size': os.path.getsize(filepath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
    
    debug_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify({
        'debug_files': debug_files,
        'debug_folder': debug_folder,
        'total_files': len(debug_files)
    })

if __name__ == '__main__':
    # 确保必要的目录存在
    for folder in [app.config['UPLOAD_FOLDER'], app.config['FURNITURE_FOLDER'], 
                   app.config['OUTPUT_FOLDER'], app.config['MASK_FOLDER'], 
                   app.config['DEBUG_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
        print(f"确保目录存在: {folder}")
    
    # 确保日志目录存在
    log_dirs = [
        os.path.join(BASE_DIR, 'project_log')
    ]
    for log_dir in log_dirs:
        os.makedirs(log_dir, exist_ok=True)
        print(f"确保日志目录存在: {log_dir}")
    
    print("调试模式：不会进行真实的大模型API调用")
    print("所有过程数据将保存到 debug/ 文件夹")
    print(f"家具文件夹路径: {app.config['FURNITURE_FOLDER']}")
    
    if os.path.exists(app.config['FURNITURE_FOLDER']):
        files = os.listdir(app.config['FURNITURE_FOLDER'])
        print(f"家具文件夹中的文件: {files}")
    else:
        print("警告: 家具文件夹不存在!")
    
    print("启动AI装修应用 v1.0 - 调试模式")
    app.run(debug=True, host='0.0.0.0', port=5001)  # 使用不同端口避免冲突