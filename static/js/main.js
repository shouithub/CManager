// 表单验证
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;
    
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = '#e74c3c';
            isValid = false;
        } else {
            input.style.borderColor = '#ddd';
        }
    });
    
    return isValid;
}

// 文件选择提示
function updateFileLabel(input, labelId) {
    const label = document.getElementById(labelId);
    if (input.files && input.files[0]) {
        label.textContent = input.files[0].name;
    }
}

// 确认删除
function confirmDelete(message = '确定要删除吗？') {
    return confirm(message);
}

// 显示消息
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(messageDiv, container.firstChild);
        
        // 3秒后自动隐藏
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 3000);
    }
}

// 全局错误处理
window.addEventListener('error', function(e) {
    console.error('全局JavaScript错误:', e.error.message);
    console.error('错误发生在:', e.filename, '行号:', e.lineno);
    console.error('错误堆栈:', e.error.stack);
    
    // 如果是submit()错误，提供更详细的信息
    if (e.error.message.includes('Cannot read properties of null (reading \'submit\')')) {
        console.error('尝试提交表单时发生错误');
        console.error('当前页面所有表单:', document.querySelectorAll('form'));
    }
});

// 加载后执行
document.addEventListener('DOMContentLoaded', function() {
    // 为所有表单添加验证
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
            let isValid = true;
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    input.style.borderColor = '#e74c3c';
                    isValid = false;
                } else {
                    input.style.borderColor = '#ddd';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('请填写所有必填项');
            }
        });
    });
});
