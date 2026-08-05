/* 共享图片裁剪脚本：驱动 _cropper_upload.html 组件，并暴露 CManagerCropper.open()。 */
(function () {
    'use strict';

    var modal = document.getElementById('cmanagerCropperModal');
    var image = document.getElementById('cmanagerCropperImage');
    var zoom = document.getElementById('cmanagerCropperZoom');
    var confirmBtn = document.getElementById('cmanagerCropperConfirm');
    var cancelBtn = document.getElementById('cmanagerCropperCancelBtn');
    var cancelIcon = document.getElementById('cmanagerCropperCancel');

    var cropper = null;
    var objectUrl = null;
    var config = null;

    function close() {
        if (cropper) { cropper.destroy(); cropper = null; }
        if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
        if (modal) {
            modal.classList.remove('open');
            modal.setAttribute('aria-hidden', 'true');
        }
        config = null;
    }

    function open(options) {
        if (!modal || !image || !zoom || !window.Cropper) {
            if (options && options.onError) options.onError('裁剪组件不可用');
            return;
        }
        config = options || {};
        if (config.objectUrl) {
            objectUrl = config.objectUrl;
            image.src = objectUrl;
        } else if (config.image) {
            if (typeof config.image === 'string') {
                image.src = config.image;
            } else {
                objectUrl = URL.createObjectURL(config.image);
                image.src = objectUrl;
            }
        }
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');

        if (cropper) cropper.destroy();
        cropper = new Cropper(image, {
            aspectRatio: config.aspectRatio || 1,
            viewMode: 1,
            dragMode: 'move',
            autoCropArea: 1,
            background: false,
            ready: function () {
                var data = cropper.getImageData();
                var ratio = data.width / data.naturalWidth;
                zoom.min = (ratio * 0.6).toFixed(4);
                zoom.max = (ratio * 3).toFixed(4);
                zoom.value = ratio.toFixed(4);
            }
        });
    }

    function confirmCrop() {
        if (!cropper || !config) return;
        var width = config.outputWidth || 512;
        var height = config.outputHeight || 512;
        var format = config.format || 'image/png';
        var quality = typeof config.quality === 'number' ? config.quality : 0.9;
        var canvas = cropper.getCroppedCanvas({
            width: width,
            height: height,
            fillColor: '#ffffff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high'
        });
        if (!canvas) {
            if (config.onError) config.onError('无法生成裁剪图片');
            return;
        }
        var onDone = config.onDone;
        var dataUrl = canvas.toDataURL(format, quality);
        canvas.toBlob(function (blob) {
            close();
            if (onDone) onDone(blob, dataUrl);
        }, format, quality);
    }

    if (confirmBtn) confirmBtn.addEventListener('click', confirmCrop);
    if (cancelBtn) cancelBtn.addEventListener('click', close);
    if (cancelIcon) cancelIcon.addEventListener('click', close);
    if (modal) {
        modal.addEventListener('click', function (event) {
            if (event.target === modal) close();
        });
    }
    if (zoom) {
        zoom.addEventListener('input', function () {
            if (cropper) cropper.zoomTo(parseFloat(zoom.value));
        });
    }
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modal && modal.classList.contains('open')) close();
    });

    window.CManagerCropper = {
        open: open,
        close: close
    };
})();
