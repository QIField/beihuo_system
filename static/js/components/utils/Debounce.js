/**
 * 防抖函数
 * 用于限制函数执行频率，常用于搜索输入等场景
 * @param {Function} fn - 要执行的函数
 * @param {number} delay - 延迟时间(ms)
 * @returns {Function}
 */
function debounce(fn, delay) {
    let timer = null;
    
    return function(...args) {
        if (timer) clearTimeout(timer);
        
        timer = setTimeout(() => {
            fn.apply(this, args);
        }, delay);
    };
}

/**
 * 节流函数
 * 用于限制函数执行频率，保证在一定时间内只执行一次
 * @param {Function} fn - 要执行的函数
 * @param {number} limit - 时间限制(ms)
 * @returns {Function}
 */
function throttle(fn, limit) {
    let inThrottle = false;
    
    return function(...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 带立即执行的防抖
 * @param {Function} fn - 要执行的函数
 * @param {number} delay - 延迟时间(ms)
 * @param {boolean} immediate - 是否立即执行
 * @returns {Function}
 */
function debounceImmediate(fn, delay, immediate = false) {
    let timer = null;
    
    return function(...args) {
        const callNow = immediate && !timer;
        
        if (timer) clearTimeout(timer);
        
        timer = setTimeout(() => {
            timer = null;
            if (!immediate) fn.apply(this, args);
        }, delay);
        
        if (callNow) fn.apply(this, args);
    };
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { debounce, throttle, debounceImmediate };
}
