/* ============================================================================
 * Material Design 3 - 主题切换系统
 * 支持浅色 / 深色 / 跟随系统 三种模式，自动保存用户偏好
 * ============================================================================ */

(function () {
    'use strict';

    const THEME_KEY = 'md3-theme-mode';
    const THEME_LIGHT = 'light';
    const THEME_DARK = 'dark';
    const THEME_AUTO = 'auto'; // 跟随系统

    // 各模式对应的 Material Icon 与提示文案
    // light -> brightness_7（太阳）
    // dark  -> brightness_4（月亮）
    // auto  -> brightness_auto（自动）

    /**
     * 获取当前系统偏好的主题
     */
    function getSystemTheme () {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? THEME_DARK : THEME_LIGHT;
    }

    /**
     * 读取用户保存的模式偏好（light / dark / auto），未设置时默认跟随系统
     */
    function getStoredTheme () {
        const saved = localStorage.getItem(THEME_KEY);
        if (saved === THEME_LIGHT || saved === THEME_DARK || saved === THEME_AUTO) {
            return saved;
        }
        return THEME_AUTO;
    }

    /**
     * 将模式解析为实际生效的主题（auto 解析为系统当前主题）
     */
    function resolveTheme (theme) {
        return theme === THEME_AUTO ? getSystemTheme() : theme;
    }

    /**
     * 应用主题到页面
     */
    function applyTheme (theme) {
        // theme 可以是 'light' | 'dark' | 'auto'
        const effective = resolveTheme(theme);

        document.documentElement.setAttribute('data-theme', effective);
        // 同步 color-scheme，保证原生控件（滚动条、表单等）与当前主题一致
        document.documentElement.style.colorScheme = effective;

        // 保存用户选择（保存的是模式，而非解析后的主题）
        localStorage.setItem(THEME_KEY, theme);

        // 更新按钮图标和提示
        updateThemeButton(theme, effective);

        // 触发自定义事件，其他组件可以监听
        document.dispatchEvent(new CustomEvent('themechange', { detail: { mode: theme, theme: effective } }));
    }

    function getTransitionOrigin (event) {
        if (event && typeof event.clientX === 'number' && typeof event.clientY === 'number') {
            return { x: event.clientX, y: event.clientY };
        }
        const toggle = document.querySelector('.sidebar-theme-toggle');
        const rect = toggle ? toggle.getBoundingClientRect() : null;
        return {
            x: rect ? rect.left + rect.width / 2 : window.innerWidth / 2,
            y: rect ? rect.top + rect.height / 2 : window.innerHeight / 2
        };
    }

    function runThemeTransition (newTheme, event) {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReduced) {
            applyTheme(newTheme);
            return;
        }

        if (!document.startViewTransition) {
            applyTheme(newTheme);
            return;
        }

        const origin = getTransitionOrigin(event);
        const maxX = Math.max(origin.x, window.innerWidth - origin.x);
        const maxY = Math.max(origin.y, window.innerHeight - origin.y);
        const radius = Math.hypot(maxX, maxY);

        const transition = document.startViewTransition(() => {
            applyTheme(newTheme);
        });

        transition.ready.then(() => {
            const start = `circle(0px at ${origin.x}px ${origin.y}px)`;
            const end = `circle(${radius}px at ${origin.x}px ${origin.y}px)`;

            document.documentElement.animate(
                { clipPath: [start, end] },
                {
                    duration: 1000,
                    easing: 'cubic-bezier(0.2, 0, 0, 1)',
                    pseudoElement: '::view-transition-new(root)'
                }
            );
        });
    }

    /**
     * 更新主题切换按钮
     */
    function updateThemeButton (theme, effective) {
        let icon, title;
        if (theme === THEME_AUTO) {
            icon = 'brightness_auto';
            title = '跟随系统（当前：' + (effective === THEME_DARK ? '深色' : '浅色') + '），点击切换';
        } else if (theme === THEME_DARK) {
            icon = 'brightness_4';
            title = '深色模式，点击切换';
        } else {
            icon = 'brightness_7';
            title = '浅色模式，点击切换';
        }

        const themeIcon = document.getElementById('theme-icon');
        if (themeIcon) {
            themeIcon.textContent = icon;
        }

        const toggle = document.querySelector('.sidebar-theme-toggle');
        if (toggle) {
            toggle.setAttribute('title', title);
            toggle.setAttribute('aria-label', title);
        }

        const themeText = document.querySelector('.sidebar-theme-toggle .theme-text');
        if (themeText) {
            themeText.textContent = theme === THEME_AUTO ? '跟随系统' : (theme === THEME_DARK ? '深色模式' : '浅色模式');
        }

        // 兼容旧版按钮
        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.textContent = icon;
            btn.classList.add('material-icons');
            btn.setAttribute('title', title);
            btn.setAttribute('aria-label', title);
        }
    }

    /**
     * 循环切换主题：浅色 -> 深色 -> 跟随系统 -> 浅色
     */
    function toggleTheme (event) {
        const current = getStoredTheme();
        let next;
        if (current === THEME_LIGHT) {
            next = THEME_DARK;
        } else if (current === THEME_DARK) {
            next = THEME_AUTO;
        } else {
            next = THEME_LIGHT;
        }
        runThemeTransition(next, event);
    }

    /**
     * 初始化主题
     */
    function initTheme () {
        const theme = getStoredTheme();
        applyTheme(theme);

        // 监听系统主题变化：仅当处于「跟随系统」模式时才同步更新
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', () => {
            if (getStoredTheme() === THEME_AUTO) {
                applyTheme(THEME_AUTO);
            }
        });
    }

    /**
     * 导出全局函数
     */
    window.toggleTheme = toggleTheme;
    window.initTheme = initTheme;
    window.getTheme = function () {
        return document.documentElement.getAttribute('data-theme') || resolveTheme(getStoredTheme());
    };
    window.getStoredTheme = getStoredTheme;

    /**
     * 页面加载时自动初始化
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
})();
