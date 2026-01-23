// 遮罩图生成工具 - 前端交互脚本

let canvas;
let uploadedImageFilename = null;
let selectedFurniture = [];

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('遮罩图生成工具初始化');
    
    // 设置文件上传事件
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', handleFileUpload);
    
    // 设置拖拽上传
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('drop', handleDrop);
});

// 处理拖拽
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

// 处理文件上传
function handleFileUpload(e) {
    const file = e.target.files[0];
    if (file) {
        uploadFile(file);
    }
}

// 上传文件到服务器
function uploadFile(file) {
    // 验证文件类型
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
        alert('不支持的文件格式，请上传 JPG、PNG 或 GIF 图片');
        return;
    }
    
    // 验证文件大小（16MB）
    if (file.size > 16 * 1024 * 1024) {
        alert('文件太大，请上传小于 16MB 的图片');
        return;
    }
    
    // 显示预览
    const reader = new FileReader();
    reader.onload = function(e) {
        const previewImage = document.getElementById('previewImage');
        previewImage.src = e.target.result;
        
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('uploadPreview').style.display = 'block';
    };
    reader.readAsDataURL(file);
    
    // 上传到服务器
    const formData = new FormData();
    formData.append('file', file);
    
    showLoading(true);
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        
        if (data.success) {
            uploadedImageFilename = data.filename;
            console.log('图片上传成功:', uploadedImageFilename);
            
            // 切换到下一步
            activateStep(2);
            loadFurnitureList();
        } else {
            alert('上传失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('上传错误:', error);
        alert('上传失败，请重试');
    });
}

// 重置上传
function resetUpload() {
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('uploadPreview').style.display = 'none';
    document.getElementById('fileInput').value = '';
    uploadedImageFilename = null;
    
    // 重置所有步骤
    activateStep(1);
    document.getElementById('furnitureSection').style.display = 'none';
    document.getElementById('editorSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'none';
    
    selectedFurniture = [];
}

// 加载家具列表
function loadFurnitureList() {
    fetch('/furniture')
    .then(response => response.json())
    .then(data => {
        const furnitureGrid = document.getElementById('furnitureGrid');
        furnitureGrid.innerHTML = '';
        
        if (data.furniture && data.furniture.length > 0) {
            data.furniture.forEach(furniture => {
                const item = document.createElement('div');
                item.className = 'furniture-item';
                item.innerHTML = `
                    <img src="${furniture.path}" alt="${furniture.name}">
                    <div class="furniture-item-name">${furniture.name}</div>
                `;
                
                item.addEventListener('click', function() {
                    selectFurniture(furniture, item);
                });
                
                furnitureGrid.appendChild(item);
            });
            
            document.getElementById('furnitureSection').style.display = 'block';
        } else {
            alert('家具库为空，请先添加家具图片到 data/furniture 目录');
        }
    })
    .catch(error => {
        console.error('加载家具列表失败:', error);
        alert('加载家具列表失败');
    });
}

// 选择家具
function selectFurniture(furniture, element) {
    // 标记为选中
    element.classList.add('selected');
    
    // 添加到选中列表（允许多次添加同一家具）
    selectedFurniture.push(furniture);
    
    updateSelectedList();
    
    // 显示编辑区域并初始化画布
    activateStep(3);
    initializeCanvas();
    
    // 立即添加到画布
    addFurnitureToCanvas(furniture);
}

// 更新已选家具列表
function updateSelectedList() {
    const list = document.getElementById('selectedFurnitureList');
    list.innerHTML = '';
    
    selectedFurniture.forEach(furniture => {
        const item = document.createElement('div');
        item.className = 'selected-item';
        item.innerHTML = `
            <span class="selected-item-name">${furniture.name}</span>
        `;
        list.appendChild(item);
    });
}

// 初始化画布
function initializeCanvas() {
    if (canvas) {
        return; // 已初始化
    }
    
    document.getElementById('editorSection').style.display = 'block';
    
    const canvasElement = document.getElementById('fabricCanvas');
    canvas = new fabric.Canvas(canvasElement, {
        width: 800,
        height: 600,
        backgroundColor: '#f0f0f0'
    });
    
    // 加载客厅背景图
    if (uploadedImageFilename) {
        const imagePath = `/user/${uploadedImageFilename}`;
        fabric.Image.fromURL(imagePath, function(img) {
            // 调整图片大小以适应画布
            const scale = Math.min(
                canvas.width / img.width,
                canvas.height / img.height
            );
            
            img.scale(scale);
            img.set({
                left: (canvas.width - img.width * scale) / 2,
                top: (canvas.height - img.height * scale) / 2,
                selectable: false,
                evented: false
            });
            
            canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
        });
    }
    
    // 监听对象选择
    canvas.on('selection:created', updateSelection);
    canvas.on('selection:updated', updateSelection);
    canvas.on('selection:cleared', updateSelection);
}

// 添加家具到画布
function addFurnitureToCanvas(furniture) {
    const imagePath = furniture.path;
    
    fabric.Image.fromURL(imagePath, function(img) {
        // 设置默认大小
        const maxSize = 150;
        const scale = Math.min(maxSize / img.width, maxSize / img.height);
        
        img.scale(scale);
        img.set({
            left: Math.random() * (canvas.width - maxSize),
            top: Math.random() * (canvas.height - maxSize),
            furnitureName: furniture.name
        });
        
        canvas.add(img);
        canvas.setActiveObject(img);
        canvas.renderAll();
    });
}

// 更新选中状态
function updateSelection() {
    const activeObject = canvas.getActiveObject();
    console.log('选中对象:', activeObject);
}

// 清空画布（保留背景）
function clearCanvas() {
    if (!canvas) return;
    
    if (confirm('确定要清空所有家具吗？')) {
        const objects = canvas.getObjects();
        objects.forEach(obj => {
            canvas.remove(obj);
        });
        canvas.renderAll();
    }
}

// 删除选中的家具
function deleteSelected() {
    if (!canvas) return;
    
    const activeObjects = canvas.getActiveObjects();
    if (activeObjects.length > 0) {
        activeObjects.forEach(obj => {
            canvas.remove(obj);
        });
        canvas.discardActiveObject();
        canvas.renderAll();
    } else {
        alert('请先选择要删除的家具');
    }
}

// 生成遮罩图
function generateMasks() {
    if (!canvas || !uploadedImageFilename) {
        alert('请先上传客厅图片并添加家具');
        return;
    }
    
    const objects = canvas.getObjects();
    if (objects.length === 0) {
        alert('请至少添加一个家具');
        return;
    }
    
    // 获取背景图的尺寸和位置
    const backgroundImage = canvas.backgroundImage;
    if (!backgroundImage) {
        alert('客厅背景图加载失败');
        return;
    }
    
    // 计算背景图的实际位置和尺寸（在Canvas中显示的尺寸）
    const bgScale = backgroundImage.scaleX;
    const bgWidth = backgroundImage.width * bgScale;
    const bgHeight = backgroundImage.height * bgScale;
    const bgLeft = backgroundImage.left;
    const bgTop = backgroundImage.top;
    
    console.log('Canvas背景图信息:', {
        width: bgWidth,
        height: bgHeight,
        left: bgLeft,
        top: bgTop
    });
    
    // 收集家具信息（相对于背景图的位置）
    const furnitureItems = [];
    objects.forEach(obj => {
        if (obj.furnitureName) {
            // 计算家具相对于背景图的位置
            const relativeLeft = obj.left - bgLeft;
            const relativeTop = obj.top - bgTop;
            
            furnitureItems.push({
                name: obj.furnitureName,
                x: Math.round(relativeLeft),
                y: Math.round(relativeTop),
                width: Math.round(obj.width * obj.scaleX),
                height: Math.round(obj.height * obj.scaleY),
                rotation: obj.angle || 0
            });
        }
    });
    
    console.log('家具信息:', furnitureItems);
    
    // 发送请求生成遮罩图，包含Canvas背景图的尺寸信息
    showLoading(true);
    
    fetch('/generate_masks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            living_room_image: uploadedImageFilename,
            furniture_items: furnitureItems,
            canvas_bg_width: Math.round(bgWidth),  // 添加Canvas中背景图的宽度
            canvas_bg_height: Math.round(bgHeight)  // 添加Canvas中背景图的高度
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        
        if (data.success) {
            console.log('生成成功:', data);
            showResult(data.composite_image, data.mask_image);
            activateStep(4);
        } else {
            alert('生成失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('生成错误:', error);
        alert('生成失败，请重试');
    });
}

// 显示结果
function showResult(compositeImagePath, maskImagePath) {
    document.getElementById('compositeImage').src = compositeImagePath;
    document.getElementById('maskImage').src = maskImagePath;
    
    document.getElementById('resultSection').style.display = 'block';
    
    // 滚动到结果区域
    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });
}

// 下载图片
function downloadImage(type) {
    let imageSrc;
    let filename;
    
    if (type === 'composite') {
        imageSrc = document.getElementById('compositeImage').src;
        filename = 'composite_' + Date.now() + '.jpg';
    } else if (type === 'mask') {
        imageSrc = document.getElementById('maskImage').src;
        filename = 'mask_' + Date.now() + '.jpg';
    }
    
    if (!imageSrc) {
        alert('图片未加载');
        return;
    }
    
    // 创建下载链接
    const link = document.createElement('a');
    link.href = imageSrc;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 重新开始
function startOver() {
    if (confirm('确定要重新开始吗？所有数据将被清空。')) {
        // 清空画布
        if (canvas) {
            canvas.dispose();
            canvas = null;
        }
        
        // 重置状态
        resetUpload();
    }
}

// 激活步骤
function activateStep(stepNumber) {
    // 移除所有active类
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step${i}`);
        if (step) {
            step.classList.remove('active');
        }
    }
    
    // 添加active类到当前步骤
    const currentStep = document.getElementById(`step${stepNumber}`);
    if (currentStep) {
        currentStep.classList.add('active');
    }
}

// 显示/隐藏加载提示
function showLoading(show) {
    const loading = document.getElementById('loading');
    loading.style.display = show ? 'flex' : 'none';
}

// 键盘事件：Delete键删除选中对象
document.addEventListener('keydown', function(e) {
    if (e.key === 'Delete' && canvas) {
        deleteSelected();
    }
});
