/* 标准文件上传组件共享脚本：驱动 _file_upload.html 的预览、移除、拖拽，
 * 并在用户浏览器内增量计算每个文件的 MD5（客户端去重）。
 *
 * MD5 值按 input.files 顺序写入同容器对应的 hidden input（name 形如
 * md5_<字段名>，值为 JSON 数组）。未计算完成时禁止表单提交，避免漏算。
 *
 * 上传进度：包含该组件的表单改为 XHR 提交（仍携带全部原生表单字段与
 * 提交按钮的 name/value），在组件内逐文件显示 MD5 计算进度与网络上传
 * 进度，并在页面顶部显示 MD3 细进度条。
 */
(function () {
    'use strict';

    var allStates = [];
    var pendingRenders = new Set();
    var rafScheduled = false;
    var uploadDisabled = new WeakSet();

    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatPercent(fraction) {
        var value = Math.max(0, Math.min(1, fraction || 0));
        return Math.round(value * 100) + '%';
    }

    function filesOf(input) {
        return Array.prototype.slice.call(input.files || []);
    }

    // 每个 input 对应一个状态：md5 缓存（File -> Promise/hex）、进度与隐藏字段
    function makeState(input) {
        var hidden = null;
        if (input.parentElement) {
            hidden = input.parentElement.querySelector('.file-md5-input');
        }
        return {
            input: input,
            hidden: hidden,
            cache: new Map(),
            pending: new Set(),
            progress: new Map(),
            uploading: false
        };
    }

    function isReady(state, file) {
        var value = state.cache.get(file);
        return typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
    }

    function fileProgress(state, file) {
        var value = state.progress.get(file);
        return typeof value === 'number' && isFinite(value)
            ? Math.max(0, Math.min(1, value))
            : 0;
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
            state.progress.delete(file);
            var promise = window.CManagerMD5.hashFile(file, function (fraction) {
                // 增量回调在浏览器本地完成，不涉及网络传输
                state.progress.set(file, fraction);
                scheduleRender(state);
            }).then(function (hex) {
                state.cache.set(file, hex);
                state.pending.delete(file);
                state.progress.set(file, 1);
                updatePendingMark(state);
                syncHidden(state);
                renderComponent(state);
            }).catch(function () {
                // 计算失败不阻塞上传：该文件按普通随机名保存（不去重）
                state.cache.delete(file);
                state.pending.delete(file);
                state.progress.delete(file);
                updatePendingMark(state);
                syncHidden(state);
                renderComponent(state);
            });
            state.cache.set(file, promise);
            state.pending.add(file);
            state.progress.set(file, 0);
        });
        updatePendingMark(state);
        syncHidden(state);
        renderComponent(state);
    }

    function updatePendingMark(state) {
        if (!state.hidden) return;
        state.hidden.dataset.pending = state.pending.size ? '1' : '';
    }

    function scheduleRender(state) {
        pendingRenders.add(state);
        if (rafScheduled) return;
        rafScheduled = true;
        requestAnimationFrame(function () {
            rafScheduled = false;
            var states = Array.prototype.slice.call(pendingRenders);
            pendingRenders.clear();
            states.forEach(renderComponent);
        });
    }

    // ---------- 组件 UI（_file_upload.html 非 simple 分支）----------

    function renderComponent(state) {
        var container = state.input.closest('.file-upload-component');
        if (!container) return;
        var area = container.querySelector('.upload-area');
        var placeholder = container.querySelector('.upload-placeholder');
        var list = container.querySelector('.file-preview-list');
        var files = filesOf(state.input);

        container.classList.toggle('is-uploading', state.uploading);

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

            var progress = fileProgress(state, file);
            if (state.uploading) {
                var uploadStatus = document.createElement('span');
                uploadStatus.className = 'file-md5-status is-uploading';
                uploadStatus.textContent = '正在上传…';
                meta.appendChild(uploadStatus);
                info.appendChild(meta);
                info.appendChild(buildProgressRow(progress));
            } else if (state.pending.has(file)) {
                var pendingStatus = document.createElement('span');
                pendingStatus.className = 'file-md5-status is-pending';
                pendingStatus.textContent = '正在计算校验值…';
                meta.appendChild(pendingStatus);
                info.appendChild(meta);
                info.appendChild(buildProgressRow(progress));
            } else if (isReady(state, file)) {
                var okStatus = document.createElement('span');
                okStatus.className = 'file-md5-status is-done';
                okStatus.title = '已校验文件内容';
                okStatus.textContent = '✓';
                meta.appendChild(okStatus);
                info.appendChild(meta);
            } else {
                var warnStatus = document.createElement('span');
                warnStatus.className = 'file-md5-status is-error';
                warnStatus.textContent = '校验值计算失败（不去重）';
                meta.appendChild(warnStatus);
                info.appendChild(meta);
            }

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'file-preview-remove';
            remove.title = '移除文件';
            remove.disabled = state.uploading;
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

    function buildProgressRow(progress) {
        var wrap = document.createElement('div');
        wrap.className = 'file-upload-progress';

        var track = document.createElement('div');
        track.className = 'file-upload-progress-track';

        var fill = document.createElement('div');
        fill.className = 'file-upload-progress-fill';
        fill.style.width = formatPercent(progress);
        track.appendChild(fill);

        var text = document.createElement('span');
        text.className = 'file-upload-progress-text';
        text.textContent = formatPercent(progress);

        wrap.appendChild(track);
        wrap.appendChild(text);
        return wrap;
    }

    function removeFile(state, index) {
        var transfer = new DataTransfer();
        var files = filesOf(state.input);
        var removed = files.splice(index, 1)[0];
        if (removed) state.progress.delete(removed);
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
        allStates.push(state);
        bindComponentEvents(state);
        computeAll(state);
        renderComponent(state);
    }

    // ---------- XHR 上传与进度 ----------

    function statesForForm(form) {
        return allStates.filter(function (state) {
            return state.input.form === form;
        });
    }

    function collectEntries(states) {
        var entries = [];
        states.forEach(function (state) {
            filesOf(state.input).forEach(function (file) {
                entries.push({
                    state: state,
                    file: file,
                    size: file.size || 0
                });
            });
        });
        return entries;
    }

    // XHR 的 progress 只给出整体已上传字节数，按各文件大小比例分摊显示
    function applyUploadFraction(entries, fraction) {
        var totalBytes = entries.reduce(function (sum, entry) { return sum + entry.size; }, 0);
        if (!totalBytes) return;
        var acc = 0;
        entries.forEach(function (entry) {
            var start = acc / totalBytes;
            acc += entry.size;
            var end = acc / totalBytes;
            var value;
            if (fraction >= end) {
                value = 1;
            } else if (fraction <= start) {
                value = 0;
            } else if (end === start) {
                value = 1;
            } else {
                value = (fraction - start) / (end - start);
            }
            entry.state.progress.set(entry.file, value);
        });
    }

    function submitterFor(event, form) {
        if (event.submitter) return event.submitter;
        var fallback = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!fallback && form.id) {
            fallback = Array.prototype.find.call(
                document.querySelectorAll('button[type="submit"], input[type="submit"]'),
                function (el) { return el.getAttribute('form') === form.id; }
            ) || null;
        }
        return fallback;
    }

    function disableFormControls(form, disabled) {
        function collect(el) {
            if (el.type === 'file') return;
            if (disabled) {
                if (!el.disabled) {
                    el.disabled = true;
                    uploadDisabled.add(el);
                }
            } else if (uploadDisabled.has(el)) {
                el.disabled = false;
                uploadDisabled.delete(el);
            }
        }
        Array.prototype.forEach.call(
            form.querySelectorAll('button, input, select, textarea'),
            collect
        );
        if (form.id) {
            Array.prototype.forEach.call(
                document.querySelectorAll('button[form], input[form]'),
                function (el) {
                    if (el.getAttribute('form') === form.id) collect(el);
                }
            );
        }
    }

    function showGlobalProgress(label) {
        var bar = document.createElement('div');
        bar.className = 'cmanager-upload-topbar';
        bar.setAttribute('role', 'progressbar');
        bar.setAttribute('aria-valuemin', '0');
        bar.setAttribute('aria-valuemax', '100');
        bar.innerHTML =
            '<div class="cmanager-upload-topbar-fill is-indeterminate"></div>' +
            '<div class="cmanager-upload-topbar-label">' +
            '<span class="cmanager-upload-topbar-text"></span></div>';
        document.body.appendChild(bar);

        var fill = bar.querySelector('.cmanager-upload-topbar-fill');
        var text = bar.querySelector('.cmanager-upload-topbar-text');
        text.textContent = label;

        return {
            update: function (fraction) {
                fill.classList.remove('is-indeterminate');
                fill.style.width = formatPercent(fraction);
                text.textContent = label + ' ' + formatPercent(fraction);
                bar.setAttribute('aria-valuenow', String(Math.round(fraction * 100)));
            },
            remove: function () {
                if (bar.parentNode) bar.parentNode.removeChild(bar);
            }
        };
    }

    function normalizedUrl(url) {
        try {
            return new URL(url, window.location.href).href;
        } catch (error) {
            return url;
        }
    }

    function replaceDocument(html) {
        if (!html) return;
        document.open();
        document.write(html);
        document.close();
    }

    function finishUpload(form, states, topBar, message) {
        delete form.dataset.cmanagerUploading;
        form.removeAttribute('aria-busy');
        disableFormControls(form, false);
        states.forEach(function (state) {
            state.uploading = false;
            state.input.disabled = false;
            renderComponent(state);
        });
        if (topBar) topBar.remove();
        if (message) alert(message);
    }

    function startUpload(form, states, event) {
        var submitter = submitterFor(event, form);
        form.dataset.cmanagerUploading = '1';
        form.setAttribute('aria-busy', 'true');

        // 必须先构建 FormData 再禁用控件，否则禁用后的文件输入会被排除
        var fd = new FormData(form);
        if (submitter && submitter.name) {
            fd.append(submitter.name, submitter.value || '');
        }

        states.forEach(function (state) {
            state.uploading = true;
            filesOf(state.input).forEach(function (file) {
                if (typeof state.progress.get(file) !== 'number') {
                    state.progress.set(file, 0);
                }
            });
            state.input.disabled = true;
            renderComponent(state);
        });
        disableFormControls(form, true);

        var entries = collectEntries(states);
        var topBar = showGlobalProgress(gettext('正在上传文件'));

        var xhr = new XMLHttpRequest();
        xhr.open(
            (form.method || 'POST').toUpperCase(),
            form.action || window.location.href,
            true
        );
        xhr.upload.addEventListener('progress', function (ev) {
            if (!ev.lengthComputable || !ev.total) return;
            var fraction = Math.min(1, ev.loaded / ev.total);
            applyUploadFraction(entries, fraction);
            states.forEach(scheduleRender);
            if (topBar) topBar.update(fraction);
        });
        xhr.addEventListener('load', function () {
            var actionUrl = normalizedUrl(form.action || window.location.href);
            var finalUrl = xhr.responseURL ? normalizedUrl(xhr.responseURL) : actionUrl;
            var contentType = (xhr.getResponseHeader('Content-Type') || '').toLowerCase();
            var isHtml = contentType.indexOf('text/html') !== -1;
            // XHR 已跟随服务端 302，若再 location.assign 一次，Django 的
            // session 消息会被中间响应消费掉，导致成功提示丢失。因此直接
            // 用最终响应替换当前文档，并把地址栏更新为最终 URL。
            if (xhr.status >= 200 && xhr.status < 300 && isHtml) {
                try {
                    var finalOrigin = new URL(finalUrl, window.location.href).origin;
                    if (finalOrigin !== window.location.origin) {
                        window.location.assign(finalUrl);
                        return;
                    }
                    // 先写入响应内容，再更新地址栏：document.open 会重建文档，
                    // 后调用 replaceState 能确保新文档的 URL 与最终地址一致。
                    replaceDocument(xhr.responseText);
                    history.replaceState(history.state, '', finalUrl);
                    return;
                } catch (error) {
                    // 跨域跳转等场景回退到普通导航
                }
            }
            window.location.assign(finalUrl);
        });
        xhr.addEventListener('error', function () {
            finishUpload(form, states, topBar, gettext('网络错误，上传失败，请重试。'));
        });
        xhr.addEventListener('abort', function () {
            finishUpload(form, states, topBar, gettext('上传已取消，请重试。'));
        });
        xhr.addEventListener('timeout', function () {
            finishUpload(form, states, topBar, gettext('上传超时，请重试。'));
        });
        xhr.send(fd);
    }

    // 页面加载时初始化所有上传输入框（组件与 simple 模式统一处理）
    document.querySelectorAll('input.file-input').forEach(initInput);

    // 提交前拦截：任一文件的 MD5 尚未计算完成时阻止提交（仅限当前表单）
    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form || form.tagName !== 'FORM') return;
        var pendingHidden = form.querySelectorAll('.file-md5-input[data-pending="1"]');
        if (pendingHidden.length) {
            event.preventDefault();
            event.stopImmediatePropagation();
            alert(gettext('正在计算文件校验值，请稍候再提交。'));
        }
    }, true);

    // 包含统一文件上传组件的表单：改为 XHR 上传以显示真实网络进度
    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form || form.tagName !== 'FORM') return;
        var states = statesForForm(form);
        if (!states.length) return;
        if (form.querySelectorAll('.file-md5-input[data-pending="1"]').length) {
            event.preventDefault();
            return;
        }
        if (form.dataset.cmanagerUploading === '1') {
            event.preventDefault();
            return;
        }
        event.preventDefault();
        startUpload(form, states, event);
    }, true);
})();
