/* 标准文件上传组件共享脚本：驱动 _file_upload.html 的预览、移除、拖拽，
 * 并在用户浏览器内增量计算每个文件的 MD5（客户端去重）。
 *
 * MD5 值按 input.files 顺序写入同容器对应的 hidden input（name 形如
 * md5_<字段名>，值为 JSON 数组）。未计算完成时禁止表单提交，避免漏算。
 */
(function () {
    'use strict';

    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function filesOf(input) {
        return Array.prototype.slice.call(input.files || []);
    }

    // 每个 input 对应一个状态：md5 缓存（File -> Promise/hex）与隐藏字段
    function makeState(input) {
        var hidden = null;
        if (input.parentElement) {
            hidden = input.parentElement.querySelector('.file-md5-input');
        }
        return {
            input: input,
            hidden: hidden,
            cache: new Map(),
            pending: new Set()
        };
    }

    function isReady(state, file) {
        var value = state.cache.get(file);
        return typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
    }

    function syncHidden(state) {
        if (!state.hidden) return;
        var md5s = filesOf(state.input).map(function (file) {
            return isReady(state, file) ? state.cache.get(file) : null;
        });
        state.hidden.value = JSON.stringify(md5s);
    }

    function computeAll(state) {
        if (!window.CManagerMD5) {
            if (state.hidden) {
                state.hidden.value = '';
                state.hidden.dataset.pending = '';
            }
            return;
        }
        state.pending.clear();
        filesOf(state.input).forEach(function (file) {
            var cached = state.cache.get(file);
            if (typeof cached === 'string') {
                return; // 已算完（同一 File 对象重新选择时复用）
            }
            if (cached) {
                return; // 已在计算中（重复 change 事件时避免并发重复计算）
            }
            var promise = window.CManagerMD5.hashFile(file).then(function (hex) {
                state.cache.set(file, hex);
                state.pending.delete(file);
                updatePendingMark(state);
                syncHidden(state);
                renderComponent(state);
            }).catch(function () {
                // 计算失败不阻塞上传：该文件按普通随机名保存（不去重）
                state.cache.delete(file);
                state.pending.delete(file);
                updatePendingMark(state);
                syncHidden(state);
                renderComponent(state);
            });
            state.cache.set(file, promise);
            state.pending.add(file);
        });
        updatePendingMark(state);
        syncHidden(state);
    }

    function updatePendingMark(state) {
        if (!state.hidden) return;
        state.hidden.dataset.pending = state.pending.size ? '1' : '';
    }

    // ---------- 组件 UI（_file_upload.html 非 simple 分支）----------

    function renderComponent(state) {
        var container = state.input.closest('.file-upload-component');
        if (!container) return;
        var area = container.querySelector('.upload-area');
        var placeholder = container.querySelector('.upload-placeholder');
        var list = container.querySelector('.file-preview-list');
        var files = filesOf(state.input);

        if (!files.length) {
            placeholder.style.display = '';
            list.style.display = 'none';
            list.innerHTML = '';
            area.classList.remove('has-file');
            return;
        }
        placeholder.style.display = 'none';
        list.style.display = 'grid';
        list.innerHTML = '';
        area.classList.add('has-file');

        files.forEach(function (file, index) {
            var item = document.createElement('div');
            item.className = 'file-preview-item';

            var icon = document.createElement('span');
            icon.className = 'material-icons file-preview-icon';
            icon.textContent = 'insert_drive_file';

            var info = document.createElement('div');
            info.className = 'file-preview-info';

            var name = document.createElement('span');
            name.className = 'file-preview-name';
            name.textContent = file.name;

            var meta = document.createElement('div');
            meta.className = 'file-preview-meta';
            var size = document.createElement('span');
            size.className = 'file-preview-size';
            size.textContent = formatSize(file.size);
            meta.appendChild(size);

            if (state.pending.has(file)) {
                var status = document.createElement('span');
                status.className = 'file-md5-status is-pending';
                status.textContent = '正在计算校验值…';
                meta.appendChild(status);
            } else if (isReady(state, file)) {
                var okStatus = document.createElement('span');
                okStatus.className = 'file-md5-status is-done';
                okStatus.title = '已校验文件内容';
                okStatus.textContent = '✓';
                meta.appendChild(okStatus);
            } else {
                var warnStatus = document.createElement('span');
                warnStatus.className = 'file-md5-status is-error';
                warnStatus.textContent = '校验值计算失败（不去重）';
                meta.appendChild(warnStatus);
            }

            info.appendChild(name);
            info.appendChild(meta);

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'file-preview-remove';
            remove.title = '移除文件';
            remove.innerHTML = '<span class="material-icons">close</span>';
            remove.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                removeFile(state, index);
            });

            item.appendChild(icon);
            item.appendChild(info);
            item.appendChild(remove);
            list.appendChild(item);
        });
    }

    function removeFile(state, index) {
        var transfer = new DataTransfer();
        var files = filesOf(state.input);
        files.splice(index, 1);
        files.forEach(function (file) { transfer.items.add(file); });
        state.input.files = transfer.files;
        computeAll(state);
        renderComponent(state);
    }

    function bindComponentEvents(state) {
        var container = state.input.closest('.file-upload-component');
        if (!container) return;
        var area = container.querySelector('.upload-area');

        state.input.addEventListener('change', function () {
            computeAll(state);
            renderComponent(state);
        });

        area.addEventListener('click', function (event) {
            if (event.target.closest('.file-preview-remove')) return;
            state.input.click();
        });

        ['dragenter', 'dragover'].forEach(function (type) {
            area.addEventListener(type, function (event) {
                event.preventDefault();
                event.stopPropagation();
                area.classList.add('drag-over');
            });
        });

        area.addEventListener('dragleave', function (event) {
            event.preventDefault();
            event.stopPropagation();
            area.classList.remove('drag-over');
        });

        area.addEventListener('drop', function (event) {
            event.preventDefault();
            event.stopPropagation();
            area.classList.remove('drag-over');
            var dropped = event.dataTransfer && event.dataTransfer.files;
            if (!dropped || !dropped.length) return;
            var transfer = new DataTransfer();
            if (state.input.multiple) {
                filesOf(state.input).forEach(function (file) { transfer.items.add(file); });
            }
            Array.prototype.forEach.call(dropped, function (file) { transfer.items.add(file); });
            state.input.files = transfer.files;
            computeAll(state);
            renderComponent(state);
        });
    }

    function initInput(input) {
        if (input.dataset.md5Initialized) return;
        input.dataset.md5Initialized = '1';
        var state = makeState(input);
        bindComponentEvents(state);
        computeAll(state);
        renderComponent(state);
    }

    // 页面加载时初始化所有上传输入框（组件与 simple 模式统一处理）
    document.querySelectorAll('input.file-input').forEach(initInput);

    // 提交前拦截：任一文件的 MD5 尚未计算完成时阻止提交
    document.addEventListener('submit', function (event) {
        var pendingHidden = document.querySelectorAll('.file-md5-input[data-pending="1"]');
        if (pendingHidden.length) {
            event.preventDefault();
            event.stopImmediatePropagation();
            alert('正在计算文件校验值，请稍候再提交。');
        }
    }, true);
})();
