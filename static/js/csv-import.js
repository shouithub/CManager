/* CSV 批量导入通用脚本：驱动 _csv_import_modal.html 组件的打开、上传与结果展示。 */
(function () {
    'use strict';

    function openModal(id) {
        var modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal(id) {
        var modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
    }

    document.addEventListener('click', function (event) {
        var opener = event.target.closest('[data-csv-import-open]');
        if (opener) {
            openModal(opener.getAttribute('data-csv-import-open'));
            return;
        }
        var closer = event.target.closest('[data-csv-import-close]');
        if (closer) {
            var modal = closer.closest('.csv-import-modal');
            if (modal) closeModal(modal.id);
            return;
        }
        if (event.target.classList && event.target.classList.contains('csv-import-modal')) {
            closeModal(event.target.id);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            document.querySelectorAll('.csv-import-modal.open').forEach(function (modal) {
                closeModal(modal.id);
            });
        }
    });

    document.querySelectorAll('.csv-import-form').forEach(function (form) {
        var fileInput = form.querySelector('input[type="file"]');
        var fileName = form.querySelector('.csv-import-file-name');
        var result = form.querySelector('.csv-import-result');
        var progress = form.querySelector('.csv-import-progress');
        var progressText = form.querySelector('.csv-import-progress-text');
        var progressBar = form.querySelector('.csv-import-progress-bar');
        var submitBtn = form.querySelector('.csv-import-submit');

        if (fileInput && fileName) {
            fileInput.addEventListener('change', function () {
                fileName.textContent = (fileInput.files && fileInput.files[0] && fileInput.files[0].name) || gettext('未选择文件');
            });
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var file = fileInput && fileInput.files && fileInput.files[0];
            if (!file) {
                result.textContent = '请先选择 CSV 文件。';
                result.className = 'csv-import-result error';
                return;
            }
            result.textContent = '';
            result.className = 'csv-import-result';
            if (progress) progress.hidden = false;
            if (progressText) progressText.textContent = '准备导入...';
            if (progressBar) progressBar.style.width = '0%';
            if (submitBtn) submitBtn.disabled = true;

            var xhr = new XMLHttpRequest();
            xhr.open('POST', form.action, true);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.timeout = 300000;

            if (xhr.upload) {
                xhr.upload.addEventListener('progress', function (event) {
                    if (event.lengthComputable) {
                        var percent = Math.round((event.loaded / event.total) * 100);
                        if (progressBar) progressBar.style.width = percent + '%';
                        if (progressText) progressText.textContent = '上传中... ' + percent + '%';
                    }
                });
            }

            xhr.addEventListener('load', function () {
                var resp = null;
                try {
                    resp = JSON.parse(xhr.responseText || '{}');
                } catch (error) {
                    resp = null;
                }
                if (xhr.status >= 200 && xhr.status < 300 && resp && resp.success) {
                    if (progressText) progressText.textContent = '导入完成';
                    if (progressBar) progressBar.style.width = '100%';
                    result.className = 'csv-import-result success';
                    result.textContent = resp.message || gettext('导入成功');
                    setTimeout(function () { window.location.reload(); }, 1500);
                } else {
                    if (progress) progress.hidden = true;
                    result.className = 'csv-import-result error';
                    result.textContent = (resp && resp.message) || gettext('导入失败，请稍后重试。');
                    if (submitBtn) submitBtn.disabled = false;
                }
            });

            xhr.addEventListener('error', function () {
                if (progress) progress.hidden = true;
                result.className = 'csv-import-result error';
                result.textContent = '网络错误，导入失败。';
                if (submitBtn) submitBtn.disabled = false;
            });

            xhr.send(new FormData(form));
        });
    });
})();
