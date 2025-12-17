/* ============================================================================
 * Material Design 3 - 主题切换系统
 * 支持浅色/深色主题切换，自动保存用户偏好
 * ============================================================================ */

(function() {
    'use strict';
    
    const THEME_KEY = 'md3-theme-mode';
    const THEME_LIGHT = 'light';
    const THEME_DARK = 'dark';
    
    /**
     * 获取当前系统偏好的主题
     */
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? THEME_DARK : THEME_LIGHT;
    }
    
    /**
     * 获取保存的主题偏好，如果没有则使用系统偏好
     */
    function getSavedTheme() {
        const saved = localStorage.getItem(THEME_KEY);
        return saved || getSystemTheme();
    }
    
    /**
     * 应用主题到页面
     */
    function applyTheme(theme) {
        // 设置 data-theme 属性
        document.documentElement.setAttribute('data-theme', theme);
        
        // 保存到 localStorage
        localStorage.setItem(THEME_KEY, theme);
        
        // 更新按钮图标和提示
        updateThemeButton(theme);
        
        // 触发自定义事件，其他组件可以监听
        document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
    }
    
    /**
     * 更新主题切换按钮
     */
    function updateThemeButton(theme) {
        // 更新侧边栏的主题图标
        const themeIcon = document.getElementById('theme-icon');
        if (themeIcon) {
            themeIcon.textContent = theme === THEME_DARK ? '☀️' : '🌙';
        }
        
        // 更新旧版按钮（如果存在）
        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.textContent = theme === THEME_DARK ? '☀️' : '🌙';
            btn.setAttribute('title', theme === THEME_DARK ? '切换到浅色模式' : '切换到深色模式');
            btn.setAttribute('aria-label', theme === THEME_DARK ? '切换到浅色模式' : '切换到深色模式');
        }
    }
    
    /**
     * 切换主题
     */
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || getSavedTheme();
        const newTheme = currentTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
        applyTheme(newTheme);
    }
    
    /**
     * 初始化主题
     */
    function initTheme() {
        const theme = getSavedTheme();
        applyTheme(theme);
        
        // 监听系统主题变化（仅在用户未手动设置主题时）
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            // 如果用户已经手动设置了主题，则不自动跟随系统
            if (!localStorage.getItem(THEME_KEY)) {
                applyTheme(e.matches ? THEME_DARK : THEME_LIGHT);
            }
        });
    }
    
    /**
     * 导出全局函数
     */
    window.toggleTheme = toggleTheme;
    window.initTheme = initTheme;
    window.getTheme = function() {
        return document.documentElement.getAttribute('data-theme') || getSavedTheme();
    };
    
    /**
     * 页面加载时自动初始化
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
    
    console.log('Theme toggle initialized. Current theme:', getSavedTheme());
})();
