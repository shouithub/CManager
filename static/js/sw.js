/**
 * CManager Service Worker
 * 只缓存 Material Icons 字体和本站上传的用户头像，加快后续页面加载速度
 * 字体来源可由管理员配置，通过 postMessage 动态更新并持久化
 *
 * 重要：fetch 事件里只拦截字体/头像这两类资源。
 * 页面 HTML、本站 CSS/JS、图片等首屏资源一律放行走网络，
 * 避免新 SW 激活接管时异步拦截在途请求，导致首次加载 CSS/JS 失败。
 */

const FONT_CACHE = 'cmanager-fonts-v1';
const LOCAL_AVATAR_CACHE = 'cmanager-local-avatars-v2';
// 旧版本遗留的头像缓存，激活时统一清理，避免历史坏响应长期滞留。
const LEGACY_AVATAR_CACHES = ['cmanager-local-avatars-v1'];
const CONFIG_CACHE = 'cmanager-sw-config-v1';

// 默认字体来源（管理员未配置时的回退）
const DEFAULT_FONT_ORIGINS = ['fonts.font.im', 'fonts.gstatic.com'];

// 内存中缓存的字体来源；初始即使用默认值，保证 fetch 处理器可以同步判断。
let _fontOrigins = [...DEFAULT_FONT_ORIGINS];

self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        await self.clients.claim();
        await Promise.all(LEGACY_AVATAR_CACHES.map(name => caches.delete(name)));
        // 从 Cache API 恢复管理员配置的字体来源，失败时继续使用默认值。
        try {
            const cache = await caches.open(CONFIG_CACHE);
            const resp = await cache.match('font-origins');
            if (resp) {
                const origins = await resp.json();
                if (Array.isArray(origins)) _fontOrigins = origins;
            }
        } catch (e) {}
    })());
});

function isCachedAvatarRequest(request) {
    if (request.method !== 'GET' || request.destination !== 'image') return false;

    const url = new URL(request.url);
    return url.origin === self.location.origin && (
        url.pathname.startsWith('/media/avatars/') ||
        url.pathname.startsWith('/cravatar/')
    );
}

async function getCachedLocalAvatar(request) {
    const cache = await caches.open(LOCAL_AVATAR_CACHE);
    const cached = await cache.match(request);
    if (cached) {
        // 只放行可用的成功响应；异常响应即使残留也不返回。
        if (cached.ok) return cached;
        try {
            await cache.delete(request);
        } catch (error) {}
    }

    const response = await fetchAvatarWithRetry(request);
    if (response.ok) {
        // 头像上传后会使用新文件名，因此可以安全地按 URL 长期复用。
        try {
            await cache.put(request, response.clone());
        } catch (error) {
            // 缓存配额不足时仍返回已下载的头像，不影响页面显示。
        }
    }
    return response;
}

async function fetchAvatarWithRetry(request) {
    const response = await fetch(request);
    // 5xx（含 Cloudflare 520 这类间歇性回源失败）重试一次，命中成功响应即返回。
    if (response.ok || response.status < 500) return response;
    return fetch(request);
}

function isFontRequest(url) {
    return _fontOrigins.some(origin => url.includes(origin));
}

// 接收来自页面的字体来源配置
self.addEventListener('message', async event => {
    if (event.data?.type === 'FONT_ORIGINS' && Array.isArray(event.data.origins)) {
        _fontOrigins = event.data.origins;
        try {
            const cache = await caches.open(CONFIG_CACHE);
            await cache.put('font-origins', new Response(JSON.stringify(_fontOrigins)));
        } catch (e) {}
    }
});

self.addEventListener('fetch', event => {
    if (isCachedAvatarRequest(event.request)) {
        event.respondWith(
            getCachedLocalAvatar(event.request).catch(() => fetch(event.request))
        );
        return;
    }

    const url = event.request.url;

    // 非字体请求（含页面 HTML、本站 CSS/JS、图片等）一律直接走网络，
    // 不在 SW 里 respondWith，避免首屏资源被异步拦截后加载失败。
    if (!isFontRequest(url)) {
        return;
    }

    event.respondWith(
        caches.open(FONT_CACHE)
            .then(cache =>
                cache.match(url).then(cached => {
                    if (cached) return cached;
                    return fetch(event.request).then(response => {
                        if (response.ok) {
                            cache.put(url, response.clone()).catch(() => {});
                        }
                        return response;
                    });
                })
            )
            // 缓存异常时回退到网络，绝不让字体资源因 SW 故障而加载失败。
            .catch(() => fetch(event.request))
    );
});
