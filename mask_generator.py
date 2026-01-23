#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遮罩图生成工具
功能：生成组合图（客厅+家具叠加）和遮罩图（家具部分为白色，背景为黑色）
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw
import json

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 配置Flask应用，指定模板和静态文件路径
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'src', 'templates'),
            static_folder=os.path.join(BASE_DIR, 'src', 'static'))
app.config['SECRET_KEY'] = 'mask-generator-secret-key'

# 配置目录
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'data', 'user')
app.config['FURNITURE_FOLDER'] = os.path.join(BASE_DIR, 'data', 'furniture')
app.config['MASK_OUTPUT_FOLDER'] = os.path.join(BASE_DIR, 'data', 'mask_img')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_message(message):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(BASE_DIR, 'project_log', 'mask_generator.log')
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")
    
    print(f"[{timestamp}] {message}")

def resize_image_if_needed(image):
    """
    如果图片高度不足512，则等比放大到高度700
    
    Args:
        image: PIL Image对象
    
    Returns:
        PIL Image对象（调整后）
    """
    width, height = image.size
    
    # 如果高度小于512，则放大到700
    if height < 512:
        target_height = 700
        scale_ratio = target_height / height
        target_width = int(width * scale_ratio)
        
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        log_message(f"图片尺寸调整: {width}x{height} -> {target_width}x{target_height} (放大{scale_ratio:.2f}倍)")
    
    return image

def create_composite_image(living_room_path, furniture_items, output_path):
    """
    创建组合图：客厅图层在最底层，家具图层在上层
    
    Args:
        living_room_path: 客厅图片路径
        furniture_items: 家具信息列表 [{"path": "...", "x": 100, "y": 200, "width": 150, "height": 200, "rotation": 0}]
        output_path: 输出图片路径
    
    Returns:
        bool: 是否成功
    """
    try:
        # 打开客厅图片
        living_room = Image.open(living_room_path).convert('RGBA')
        
        # 如果高度不足512，等比放大到700
        living_room = resize_image_if_needed(living_room)
        width, height = living_room.size
        
        # 创建组合图，客厅作为底层
        composite = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        composite.paste(living_room, (0, 0))
        
        # 叠加家具图层
        for item in furniture_items:
            if not os.path.exists(item['path']):
                log_message(f"警告：家具文件不存在 - {item['path']}")
                continue
            
            # 打开家具图片
            furniture = Image.open(item['path']).convert('RGBA')
            
            # 调整家具大小
            furniture_width = int(item.get('width', furniture.width))
            furniture_height = int(item.get('height', furniture.height))
            furniture = furniture.resize((furniture_width, furniture_height), Image.Resampling.LANCZOS)
            
            # 旋转家具（如果需要）
            rotation = item.get('rotation', 0)
            if rotation != 0:
                furniture = furniture.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
            
            # 计算粘贴位置（居中对齐）
            x = int(item.get('x', 0))
            y = int(item.get('y', 0))
            
            # 粘贴家具到组合图
            composite.paste(furniture, (x, y), furniture)
        
        # 转换为RGB模式并保存为JPG
        composite_rgb = Image.new('RGB', composite.size, (255, 255, 255))
        composite_rgb.paste(composite, mask=composite.split()[3] if composite.mode == 'RGBA' else None)
        composite_rgb.save(output_path, 'JPEG', quality=95)
        
        log_message(f"组合图生成成功: {output_path}")
        return True
        
    except Exception as e:
        log_message(f"生成组合图失败: {str(e)}")
        return False

def create_mask_image(living_room_path, furniture_items, output_path):
    """
    创建遮罩图：家具部分为白色(255)，背景部分为黑色(0)
    
    Args:
        living_room_path: 客厅图片路径（用于获取尺寸）
        furniture_items: 家具信息列表
        output_path: 输出遮罩图路径
    
    Returns:
        bool: 是否成功
    """
    try:
        # 打开客厅图片获取尺寸
        living_room = Image.open(living_room_path)
        
        # 如果高度不足512，等比放大到700
        living_room = resize_image_if_needed(living_room)
        width, height = living_room.size
        
        # 创建黑色背景（全黑）
        mask = Image.new('L', (width, height), 0)  # 'L' mode for grayscale, 0 = black
        
        # 在遮罩上绘制白色家具区域
        for item in furniture_items:
            if not os.path.exists(item['path']):
                log_message(f"警告：家具文件不存在 - {item['path']}")
                continue
            
            # 打开家具图片
            furniture = Image.open(item['path']).convert('RGBA')
            
            # 调整家具大小
            furniture_width = int(item.get('width', furniture.width))
            furniture_height = int(item.get('height', furniture.height))
            furniture = furniture.resize((furniture_width, furniture_height), Image.Resampling.LANCZOS)
            
            # 旋转家具（如果需要）
            rotation = item.get('rotation', 0)
            if rotation != 0:
                furniture = furniture.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
            
            # 创建家具的遮罩（基于alpha通道）
            furniture_mask = furniture.split()[3] if furniture.mode == 'RGBA' else Image.new('L', furniture.size, 255)
            
            # 创建临时白色图层
            white_layer = Image.new('L', furniture.size, 255)
            
            # 计算粘贴位置
            x = int(item.get('x', 0))
            y = int(item.get('y', 0))
            
            # 将白色家具区域粘贴到遮罩图
            mask.paste(white_layer, (x, y), furniture_mask)
        
        # 保存遮罩图为JPG格式（转换为RGB）
        mask_rgb = Image.new('RGB', mask.size)
        mask_rgb.paste(mask)
        mask_rgb.save(output_path, 'JPEG', quality=95)
        
        log_message(f"遮罩图生成成功: {output_path}")
        return True
        
    except Exception as e:
        log_message(f"生成遮罩图失败: {str(e)}")
        return False

@app.route('/')
def index():
    """主页面"""
    return render_template('mask_generator.html')

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
            
            log_message(f"用户上传图片: {unique_filename}")
            
            return jsonify({
                'success': True,
                'filename': unique_filename,
                'message': '图片上传成功'
            })
        else:
            return jsonify({'error': '不支持的文件格式'}), 400
            
    except Exception as e:
        log_message(f"上传文件错误: {str(e)}")
        return jsonify({'error': '上传失败'}), 500

@app.route('/furniture')
def get_furniture_list():
    """获取家具库列表"""
    try:
        furniture_folder = app.config['FURNITURE_FOLDER']
        furniture_list = []
        
        if os.path.exists(furniture_folder):
            files = os.listdir(furniture_folder)
            
            for filename in files:
                if allowed_file(filename):
                    furniture_list.append({
                        'name': filename,
                        'path': f'/furniture/{filename}'
                    })
        
        return jsonify({'furniture': furniture_list})
        
    except Exception as e:
        log_message(f"获取家具列表错误: {str(e)}")
        return jsonify({'error': '获取家具列表失败'}), 500

@app.route('/furniture/<filename>')
def serve_furniture(filename):
    """提供家具图片"""
    return send_from_directory(app.config['FURNITURE_FOLDER'], filename)

@app.route('/user/<filename>')
def serve_user_image(filename):
    """提供用户上传的图片"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/mask_img/<filename>')
def serve_mask_image(filename):
    """提供生成的遮罩图和组合图"""
    return send_from_directory(app.config['MASK_OUTPUT_FOLDER'], filename)

@app.route('/generate_masks', methods=['POST'])
def generate_masks():
    """生成组合图和遮罩图"""
    try:
        data = request.get_json()
        
        # 获取客厅图片路径
        living_room_filename = data.get('living_room_image')
        if not living_room_filename:
            return jsonify({'error': '未提供客厅图片'}), 400
        
        living_room_path = os.path.join(app.config['UPLOAD_FOLDER'], living_room_filename)
        if not os.path.exists(living_room_path):
            return jsonify({'error': '客厅图片不存在'}), 400
        
        # 获取家具信息
        furniture_data = data.get('furniture_items', [])
        if not furniture_data:
            return jsonify({'error': '未提供家具信息'}), 400
        
        # 获取前端Canvas中的背景图尺寸信息
        canvas_bg_width = data.get('canvas_bg_width', 0)
        canvas_bg_height = data.get('canvas_bg_height', 0)
        
        # 读取原始图片并计算放大后的尺寸
        original_image = Image.open(living_room_path)
        original_width, original_height = original_image.size
        
        # 计算放大后的尺寸（与resize_image_if_needed逻辑一致）
        if original_height < 512:
            target_height = 700
            scale_ratio = target_height / original_height
            target_width = int(original_width * scale_ratio)
        else:
            target_width = original_width
            target_height = original_height
        
        log_message(f"原始图片尺寸: {original_width}x{original_height}, 目标尺寸: {target_width}x{target_height}")
        log_message(f"Canvas背景图尺寸: {canvas_bg_width}x{canvas_bg_height}")
        
        # 计算坐标缩放比例（从Canvas坐标到实际图片坐标）
        if canvas_bg_width > 0 and canvas_bg_height > 0:
            coord_scale_x = target_width / canvas_bg_width
            coord_scale_y = target_height / canvas_bg_height
            log_message(f"坐标缩放比例: X={coord_scale_x:.3f}, Y={coord_scale_y:.3f}")
        else:
            # 如果前端没有传递Canvas尺寸，使用默认比例1
            coord_scale_x = 1.0
            coord_scale_y = 1.0
            log_message("警告：未收到Canvas背景图尺寸，使用默认缩放比例1.0")
        
        # 处理家具信息，添加完整路径并调整坐标
        furniture_items = []
        for item in furniture_data:
            furniture_name = item.get('name')
            if furniture_name:
                furniture_path = os.path.join(app.config['FURNITURE_FOLDER'], furniture_name)
                
                # 调整坐标和尺寸（从Canvas坐标系转换到实际图片坐标系）
                original_x = item.get('x', 0)
                original_y = item.get('y', 0)
                original_width_item = item.get('width', 100)
                original_height_item = item.get('height', 100)
                
                adjusted_x = int(original_x * coord_scale_x)
                adjusted_y = int(original_y * coord_scale_y)
                adjusted_width = int(original_width_item * coord_scale_x)
                adjusted_height = int(original_height_item * coord_scale_y)
                
                log_message(f"家具 {furniture_name}: Canvas坐标({original_x},{original_y},{original_width_item},{original_height_item}) -> 实际坐标({adjusted_x},{adjusted_y},{adjusted_width},{adjusted_height})")
                
                furniture_items.append({
                    'path': furniture_path,
                    'x': adjusted_x,
                    'y': adjusted_y,
                    'width': adjusted_width,
                    'height': adjusted_height,
                    'rotation': item.get('rotation', 0)
                })
        
        # 生成唯一的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        composite_filename = f"composite_{timestamp}.jpg"
        mask_filename = f"mask_{timestamp}.jpg"
        
        composite_path = os.path.join(app.config['MASK_OUTPUT_FOLDER'], composite_filename)
        mask_path = os.path.join(app.config['MASK_OUTPUT_FOLDER'], mask_filename)
        
        # 确保输出目录存在
        os.makedirs(app.config['MASK_OUTPUT_FOLDER'], exist_ok=True)
        
        # 生成组合图
        composite_success = create_composite_image(living_room_path, furniture_items, composite_path)
        if not composite_success:
            return jsonify({'error': '生成组合图失败'}), 500
        
        # 生成遮罩图
        mask_success = create_mask_image(living_room_path, furniture_items, mask_path)
        if not mask_success:
            return jsonify({'error': '生成遮罩图失败'}), 500
        
        # 保存生成记录
        record = {
            'timestamp': datetime.now().isoformat(),
            'living_room': living_room_filename,
            'furniture_count': len(furniture_items),
            'composite_image': composite_filename,
            'mask_image': mask_filename,
            'furniture_details': furniture_data
        }
        
        record_file = os.path.join(app.config['MASK_OUTPUT_FOLDER'], f"record_{timestamp}.json")
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        
        log_message(f"成功生成组合图和遮罩图: {composite_filename}, {mask_filename}")
        
        return jsonify({
            'success': True,
            'composite_image': f'/mask_img/{composite_filename}',
            'mask_image': f'/mask_img/{mask_filename}',
            'message': '组合图和遮罩图生成成功'
        })
        
    except Exception as e:
        log_message(f"生成遮罩图错误: {str(e)}")
        return jsonify({'error': f'生成失败: {str(e)}'}), 500

if __name__ == '__main__':
    # 确保必要的目录存在
    for folder in [app.config['UPLOAD_FOLDER'], app.config['FURNITURE_FOLDER'], 
                   app.config['MASK_OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
        print(f"确保目录存在: {folder}")
    
    # 确保日志目录存在
    log_dir = os.path.join(BASE_DIR, 'project_log')
    os.makedirs(log_dir, exist_ok=True)
    print(f"确保日志目录存在: {log_dir}")
    
    print(f"遮罩图生成工具启动")
    print(f"输出目录: {app.config['MASK_OUTPUT_FOLDER']}")
    
    app.run(debug=True, host='0.0.0.0', port=5002)
