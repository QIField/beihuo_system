/**
 * 频次数据前端处理模块
 *
 * 职责：
 * 1. 解析日期范围字符串（yyyy-MM-dd - yyyy-MM-dd）
 * 2. 将后端返回的频次数据合并到表格行中
 * 3. 提供统一的加载状态提示
 * 4. 处理无匹配数据、日期格式错误等异常情况
 *
 * 说明：
 * - 实际频次计算在服务端完成（参见 app/services/sales_frequency_service.py）
 * - 本模块主要负责前端数据整合与交互状态管理
 */

(function(root, factory) {
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = factory();
    } else if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else {
        root.FrequencyModule = factory();
    }
})(this, function() {
    'use strict';

    /**
     * 解析日期范围字符串
     * @param {string} dateRangeStr 格式：yyyy-MM-dd - yyyy-MM-dd
     * @returns {{start: string, end: string}} 开始/结束日期
     */
    function parseDateRange(dateRangeStr) {
        if (!dateRangeStr || typeof dateRangeStr !== 'string') {
            return { start: '', end: '' };
        }
        var dates = dateRangeStr.split(' - ');
        if (dates.length === 2) {
            return {
                start: dates[0].trim(),
                end: dates[1].trim()
            };
        }
        return { start: '', end: '' };
    }

    /**
     * 校验日期字符串是否合法
     * @param {string} dateStr 日期字符串
     * @returns {boolean}
     */
    function isValidDate(dateStr) {
        if (!dateStr) return false;
        var regex = /^\d{4}-\d{2}-\d{2}$/;
        if (!regex.test(dateStr)) return false;
        var date = new Date(dateStr + 'T00:00:00');
        return !isNaN(date.getTime());
    }

    /**
     * 将频次数据合并到表格行中
     *
     * @param {Array} rows 表格行数据
     * @param {Object} frequencyMap 频次映射 {barcode: count}
     * @param {string} barcodeField 物料条码字段名，默认 '物料条码'
     * @param {string} frequencyField 频次字段名，默认 'frequency'
     * @returns {Array} 合并后的行数据
     */
    function mergeFrequencyIntoRows(rows, frequencyMap, barcodeField, frequencyField) {
        barcodeField = barcodeField || '物料条码';
        frequencyField = frequencyField || 'frequency';

        if (!Array.isArray(rows)) {
            return rows;
        }

        if (!frequencyMap || typeof frequencyMap !== 'object') {
            rows.forEach(function(row) {
                row[frequencyField] = row[frequencyField] !== undefined ? row[frequencyField] : '';
            });
            return rows;
        }

        rows.forEach(function(row) {
            var barcode = row[barcodeField];
            if (barcode && frequencyMap.hasOwnProperty(barcode)) {
                row[frequencyField] = frequencyMap[barcode];
            } else if (row[frequencyField] === undefined) {
                row[frequencyField] = barcode ? 0 : '';
            }
        });

        return rows;
    }

    /**
     * 显示频次加载状态
     * @param {string|number} loadingIndex 已有的 layer.load 索引，可选
     * @returns {string|number} layer.load 索引
     */
    function showLoading(loadingIndex) {
        if (typeof layui !== 'undefined' && layui.layer) {
            if (loadingIndex !== undefined) {
                layui.layer.close(loadingIndex);
            }
            return layui.layer.load(2, {
                content: '正在计算频次...',
                shade: [0.1, '#fff']
            });
        }
        return undefined;
    }

    /**
     * 关闭频次加载状态
     * @param {string|number} loadingIndex layer.load 索引
     */
    function hideLoading(loadingIndex) {
        if (loadingIndex !== undefined && typeof layui !== 'undefined' && layui.layer) {
            layui.layer.close(loadingIndex);
        }
    }

    /**
     * 显示频次相关提示信息
     * @param {string} msg 提示内容
     * @param {number} icon 图标类型，默认 0
     */
    function showMsg(msg, icon) {
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.msg(msg, { icon: icon || 0 });
        }
    }

    /**
     * 格式化频次显示值
     * - 数字直接返回
     * - 空字符串/undefined 返回空字符串
     *
     * @param {*} value
     * @returns {string|number}
     */
    function formatFrequencyValue(value) {
        if (value === '' || value === null || value === undefined) {
            return '';
        }
        var num = parseFloat(value);
        return isNaN(num) ? '' : num;
    }

    return {
        parseDateRange: parseDateRange,
        isValidDate: isValidDate,
        mergeFrequencyIntoRows: mergeFrequencyIntoRows,
        showLoading: showLoading,
        hideLoading: hideLoading,
        showMsg: showMsg,
        formatFrequencyValue: formatFrequencyValue
    };
});