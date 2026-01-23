// 全局变量
let canvas;
let uploadedImage = null;
let selectedFurniture = [];
let furnitureList = [];

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupFileUpload();
    setupDragAndDrop();
    loadFurnitureList();
    setupCategoryFilters();
}

// 设置文件上传
function setupFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadArea');
    
    fileInput.addEventListener('change', handleFileSelect);
    
    // 点击上传区域触发文件选择
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
}

// 设置拖拽上传
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
}

// 处理文件选择
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

// 处理文件上传
function handleFile(file) {
    // 验证文件类型
    if (!file.type.startsWith('image/')) {
        alert('请选择图片文件！');
        return;
    }
    
    // 验证文件大小 (16MB)
    if (file.size > 16 * 1024 * 1024) {
        alert('文件大小不能超过16MB！');
        return;
    }
    
    // 显示预览
    const reader = new FileReader();
    reader.onload = function(e) {
        showImagePreview(e.target.result);
    };
    reader.readAsDataURL(file);
    
    // 上传文件
    uploadFile(file);
}

// 显示图片预览
function showImagePreview(imageSrc) {
    const uploadSection = document.getElementById('uploadSection');
    const uploadArea = document.getElementById('uploadArea');
    const uploadPreview = document.getElementById('uploadPreview');
    const previewImage = document.getElementById('previewImage');
    
    previewImage.src = imageSrc;
    uploadArea.style.display = 'none';
    uploadPreview.style.display = 'block';
    
    // 激活下一步
    activateStep(2);
    showSection('furnitureSection');
    
    // 确保家具列表已加载
    console.log('图片上传完成，加载家具列表...');
    loadFurnitureList();
}

// 上传文件到服务器
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            uploadedImage = data.filename;
            console.log('文件上传成功:', data.filename);
        } else {
            alert('上传失败: ' + data.error);
        }
    })
    .catch(error => {
        console.error('上传错误:', error);
        alert('上传失败，请重试');
    });
}

// 重置上传
function resetUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadPreview = document.getElementById('uploadPreview');
    const fileInput = document.getElementById('fileInput');
    
    uploadArea.style.display = 'block';
    uploadPreview.style.display = 'none';
    fileInput.value = '';
    uploadedImage = null;
    
    // 重置步骤
    activateStep(1);
    hideAllSections();
}

// 加载家具列表
function loadFurnitureList() {
    console.log('开始加载家具列表...');
    
    fetch('/furniture')
    .then(response => {
        console.log('家具API响应状态:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('收到家具数据:', data);
        furnitureList = data.furniture || [];
        displayFurniture(furnitureList);
    })
    .catch(error => {
        console.error('加载家具列表失败:', error);
        // 显示错误信息给用户
        const furnitureGrid = document.getElementById('furnitureGrid');
        if (furnitureGrid) {
            furnitureGrid.innerHTML = '<p style="color: red;">加载家具列表失败，请刷新页面重试</p>';
        }
    });
}

// 显示家具
function displayFurniture(furniture) {
    console.log('显示家具列表:', furniture);
    
    const furnitureGrid = document.getElementById('furnitureGrid');
    if (!furnitureGrid) {
        console.error('找不到家具网格元素');
        return;
    }
    
    furnitureGrid.innerHTML = '';
    
    if (!furniture || furniture.length === 0) {
        furnitureGrid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 40px;">
                <p>暂无家具，请在 data/furniture 目录中添加家具图片</p>
                <p style="font-size: 14px; color: #666;">支持格式：JPG、PNG、GIF</p>
            </div>
        `;
        return;
    }
    
    furniture.forEach((item, index) => {
        console.log(`创建家具项 ${index}:`, item);
        
        const furnitureItem = document.createElement('div');
        furnitureItem.className = 'furniture-item';
        furnitureItem.innerHTML = `
            <img src="${item.path}" alt="${item.name}" 
                 onerror="console.error('图片加载失败:', '${item.path}'); this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjEyIiBmaWxsPSIjOTk5IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+5Zu+54mH</text></svg>'"
                 onload="console.log('图片加载成功:', '${item.path}')">
            <p>${item.name}</p>
        `;
        
        furnitureItem.addEventListener('click', () => {
            console.log('选择家具:', item);
            selectFurniture(item, furnitureItem);
        });
        
        furnitureGrid.appendChild(furnitureItem);
    });
    
    console.log(`显示了 ${furniture.length} 个家具项`);
}

// 选择家具
function selectFurniture(furniture, element) {
    element.classList.toggle('selected');
    
    const index = selectedFurniture.findIndex(item => item.name === furniture.name);
    if (index > -1) {
        selectedFurniture.splice(index, 1);
    } else {
        selectedFurniture.push(furniture);
    }
    
    updateSelectedFurnitureList();
    
    // 如果有选中的家具，激活下一步
    if (selectedFurniture.length > 0) {
        activateStep(3);
        showSection('editorSection');
        initializeCanvas();
    }
}

// 更新已选择家具列表
function updateSelectedFurnitureList() {
    const listContainer = document.getElementById('selectedFurnitureList');
    listContainer.innerHTML = '';
    
    selectedFurniture.forEach(furniture => {
        const listItem = document.createElement('div');
        listItem.className = 'furniture-list-item';
        listItem.innerHTML = `
            <img src="${furniture.path}" alt="${furniture.name}">
            <span>${furniture.name}</span>
        `;
        
        listItem.addEventListener('click', () => {
            addFurnitureToCanvas(furniture);
        });
        
        listContainer.appendChild(listItem);
    });
}

// 设置分类过滤器
function setupCategoryFilters() {
    const categoryButtons = document.querySelectorAll('.category-btn');
    
    categoryButtons.forEach(button => {
        button.addEventListener('click', () => {
            // 更新按钮状态
            categoryButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // 过滤家具
            const category = button.dataset.category;
            filterFurniture(category);
        });
    });
}

// 过滤家具
function filterFurniture(category) {
    let filteredFurniture = furnitureList;
    
    if (category !== 'all') {
        filteredFurniture = furnitureList.filter(item => 
            item.name.toLowerCase().includes(category.toLowerCase())
        );
    }
    
    displayFurniture(filteredFurniture);
}

// 初始化画布
function initializeCanvas() {
    if (canvas) {
        canvas.dispose();
    }
    
    const canvasElement = document.getElementById('fabricCanvas');
    canvas = new fabric.Canvas('fabricCanvas', {
        width: 800,
        height: 600,
        backgroundColor: '#f0f0f0'
    });
    
    // 如果有上传的图片，设置为背景
    if (uploadedImage) {
        fabric.Image.fromURL(`/user/${uploadedImage}`, function(img) {
            // 计算缩放比例以适应画布
            const scaleX = canvas.width / img.width;
            const scaleY = canvas.height / img.height;
            const scale = Math.min(scaleX, scaleY);
            
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
}

// 添加家具到画布
function addFurnitureToCanvas(furniture) {
    fabric.Image.fromURL(furniture.path, function(img) {
        // 设置家具大小
        const maxSize = 100;
        const scale = Math.min(maxSize / img.width, maxSize / img.height);
        
        img.scale(scale);
        img.set({
            left: Math.random() * (canvas.width - img.width * scale),
            top: Math.random() * (canvas.height - img.height * scale),
            cornerColor: '#667eea',
            cornerSize: 10,
            transparentCorners: false
        });
        
        canvas.add(img);
        canvas.setActiveObject(img);
        canvas.renderAll();
    });
}

// 清空画布
function clearCanvas() {
    if (canvas) {
        canvas.getObjects().forEach(obj => {
            if (obj !== canvas.backgroundImage) {
                canvas.remove(obj);
            }
        });
        canvas.renderAll();
    }
}

// 删除选中对象
function deleteSelected() {
    if (canvas) {
        const activeObjects = canvas.getActiveObjects();
        activeObjects.forEach(obj => {
            canvas.remove(obj);
        });
        canvas.discardActiveObject();
        canvas.renderAll();
    }
}

// 生成装修效果图
function generateDecoration() {
    if (!uploadedImage) {
        alert('请先上传客厅照片！');
        return;
    }
    
    if (selectedFurniture.length === 0) {
        alert('请先选择家具！');
        return;
    }
    
    // 收集画布上的家具信息
    const furniturePositions = [];
    canvas.getObjects().forEach(obj => {
        if (obj !== canvas.backgroundImage) {
            furniturePositions.push({
                left: obj.left,
                top: obj.top,
                scaleX: obj.scaleX,
                scaleY: obj.scaleY,
                angle: obj.angle
            });
        }
    });
    
    const requestData = {
        original_image: uploadedImage,
        furniture_selections: selectedFurniture,
        furniture_positions: furniturePositions
    };
    
    // 显示加载动画
    showLoading();
    updateLoadingMessage('正在提交生成请求...');
    
    // 调用生成API
    fetch('/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            showResult(data.generated_image);
            activateStep(4);
        } else {
            alert('生成失败: ' + data.error);
        }
    })
    .catch(error => {
        hideLoading();
        console.error('生成错误:', error);
        alert('生成失败，请重试');
    });
}

// 显示结果
function showResult(imagePath) {
    const resultImage = document.getElementById('resultImage');
    resultImage.src = imagePath;
    
    showSection('resultSection');
}

// 下载结果
function downloadResult() {
    const resultImage = document.getElementById('resultImage');
    const link = document.createElement('a');
    link.href = resultImage.src;
    link.download = 'decoration_result.jpg';
    link.click();
}

// 重新开始
function startOver() {
    // 重置所有状态
    uploadedImage = null;
    selectedFurniture = [];
    
    // 清空选择状态
    document.querySelectorAll('.furniture-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // 重置上传
    resetUpload();
    
    // 隐藏所有区域
    hideAllSections();
}

// 工具函数
function activateStep(stepNumber) {
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    document.getElementById(`step${stepNumber}`).classList.add('active');
}

function showSection(sectionId) {
    document.getElementById(sectionId).style.display = 'block';
}

function hideAllSections() {
    const sections = ['furnitureSection', 'editorSection', 'resultSection'];
    sections.forEach(sectionId => {
        document.getElementById(sectionId).style.display = 'none';
    });
}

function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function updateLoadingMessage(message) {
    const loadingElement = document.getElementById('loading');
    const messageElement = loadingElement.querySelector('p');
    if (messageElement) {
        messageElement.textContent = message;
    }
}