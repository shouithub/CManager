/**
 * CManager Service Worker
 * 缓存 Material Icons 字体资源，加快后续页面加载速度
 * 字体来源可由管理员配置，通过 postMessage 动态更新并持久化
 */

const FONT_CACHE = 'cmanager-fonts-v1';
const CONFIG_CACHE = 'cmanager-sw-config-v1';

// 默认字体来源（管理员未配置时的回退）
const DEFAULT_FONT_ORIGINS = ['fonts.font.im', 'fonts.gstatic.com'];

// 内存中缓存的字体来源（SW 重启后从 Cache API 恢复）
let _fontOrigins = null;

async function getFontOrigins() {
    if (_fontOrigins !== null) return _fontOrigins;
    try {
        const cache = await caches.open(CONFIG_CACHE);
        const resp = await cache.match('font-origins');
        if (resp) {
            _fontOrigins = await resp.json();
            return _fontOrigins;
        }
    } catch (e) {}
    _fontOrigins = DEFAULT_FONT_ORIGINS;
    return _fontOrigins;
}

// 接收来自页面的字体来源配置
self.addEventListener('message', async event => {
    if (event.data?.type === 'FONT_ORIGINS') {
        _fontOrigins = event.data.origins;
        try {
            const cache = await caches.open(CONFIG_CACHE);
            await cache.put('font-origins', new Response(JSON.stringify(_fontOrigins)));
        } catch (e) {}
    }
});

self.addEventListener('fetch', event => {
    const url = event.request.url;

    // 快速同步预判：已加载来源配置时直接跳过非字体请求
    if (_fontOrigins !== null && !_fontOrigins.some(origin => url.includes(origin))) {
        return;
    }

    event.respondWith(
        getFontOrigins().then(origins => {
            if (!origins.some(origin => url.includes(origin))) {
                return fetch(event.request);
            }
            return caches.open(FONT_CACHE).then(cache =>
                cache.match(url).then(cached => {
                    if (cached) return cached;
                    return fetch(event.request).then(response => {
                        if (response.ok) cache.put(url, response.clone());
                        return response;
                    }).catch(err => Promise.reject(err));
                })
            );
        })
    );
});
