/* 标准文件上传组件共享脚本：驱动 _file_upload.html 的预览、移除与拖拽。 */
(function () {
    'use strict';

    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function init(container) {
        var input = container.querySelector('.file-input');
        var area = container.querySelector('.upload-area');
        var placeholder = container.querySelector('.upload-placeholder');
        var list = container.querySelector('.file-preview-list');
        if (!input || !area || !placeholder || !list) return;

        function filesOf() {
            return Array.prototype.slice.call(input.files || []);
        }

        function render() {
            var files = filesOf();
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
                var size = document.createElement('span');
                size.className = 'file-preview-size';
                size.textContent = formatSize(file.size);
                info.appendChild(name);
                info.appendChild(size);

                var remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'file-preview-remove';
                remove.title = '移除文件';
                remove.innerHTML = '<span class="material-icons">close</span>';
                remove.addEventListener('click', function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    removeFile(index);
                });

                item.appendChild(icon);
                item.appendChild(info);
                item.appendChild(remove);
                list.appendChild(item);
            });
        }

        function removeFile(index) {
            var transfer = new DataTransfer();
            var files = filesOf();
            files.splice(index, 1);
            files.forEach(function (file) { transfer.items.add(file); });
            input.files = transfer.files;
            render();
        }

        input.addEventListener('change', render);

        area.addEventListener('click', function (event) {
            if (event.target.closest('.file-preview-remove')) return;
            input.click();
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
            if (input.multiple) {
                filesOf().forEach(function (file) { transfer.items.add(file); });
            }
            Array.prototype.forEach.call(dropped, function (file) { transfer.items.add(file); });
            input.files = transfer.files;
            render();
        });

        render();
    }

    document.querySelectorAll('.file-upload-component').forEach(init);
})();
