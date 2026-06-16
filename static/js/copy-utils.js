/**
 * 通用复制工具 - 自动处理替换号列格式
 * 所有页面复制功能都应调用此工具
 */

// 替换号列关键词列表
const REPLACE_KEYWORDS = ['替换号', 'replace_number', 'replaceNumber'];

/**
 * 判断是否是替换号相关列
 * @param {string} field - 列字段名
 * @param {string} headerName - 列标题名
 * @returns {boolean}
 */
function isReplaceNumberColumn(field, headerName) {
    const replaceKeywords = ['替换号', 'replace_number', 'replaceNumber'];
    if (field) {
        return replaceKeywords.some(kw => field.toLowerCase().includes(kw.toLowerCase()));
    }
    if (headerName) {
        return replaceKeywords.some(kw => headerName.includes(kw));
    }
    return false;
}

/**
 * 格式化替换号内容：逗号/中文逗号 → 换行
 * @param {*} value - 原始值
 * @returns {string}
 */
function formatReplaceNumberValue(value) {
    if (!value) return value;
    return String(value)
        .replace(/，/g, '\n')
        .replace(/,/g, '\n')
        .replace(/^\s+|\s+$/g, '');
}

/**
 * 通用复制入口：根据列类型自动决定是否格式化
 * @param {*} value - 原始值
 * @param {string} field - 列字段名
 * @param {string} headerName - 列标题名
 * @returns {string}
 */
function processCopyValue(value, field, headerName) {
    if (isReplaceNumberColumn(field, headerName)) {
        return formatReplaceNumberValue(value);
    }
    return value;
}

/**
 * 复制文本到剪贴板（统一封装）
 * @param {string} text - 要复制的文本
 * @param {Function} onSuccess - 成功回调
 * @param {Function} onError - 失败回调
 */
function copyToClipboardUniversal(text, onSuccess, onError) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(String(text)).then(function() {
            if (onSuccess) onSuccess();
        }).catch(function(err) {
            fallbackCopyToClipboard(text, onSuccess, onError);
        });
    } else {
        fallbackCopyToClipboard(text, onSuccess, onError);
    }
}

/**
 * 兼容性复制到剪贴板
 * @param {string} text - 要复制的文本
 * @param {Function} onSuccess - 成功回调
 * @param {Function} onError - 失败回调
 */
function fallbackCopyToClipboard(text, onSuccess, onError) {
    const textarea = document.createElement('textarea');
    textarea.value = String(text);
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
        const success = document.execCommand('copy');
        if (success) {
            if (onSuccess) onSuccess();
        } else {
            if (onError) onError();
        }
    } catch (err) {
        if (onError) onError(err);
    }

    document.body.removeChild(textarea);
}
