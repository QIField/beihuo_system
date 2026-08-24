/**
 * 发动机底盘统计统一表格配置
 *
 * 为 HandsontableBuilder 提供发动机型号统计和底盘型号统计两个表格的配置。
 */

window.EngineChassisStatsConfig = (function() {
    'use strict';

    /**
     * 从日期范围输入框获取起止日期
     */
    function getDateRange() {
        var el = document.getElementById('dateRange');
        if (!el || !el.value) {
            return { start_date: '', end_date: '' };
        }
        var dates = el.value.split(' - ');
        return { start_date: dates[0] || '', end_date: dates[1] || '' };
    }

    /**
     * 发动统计表格列定义
     */
    function buildEngineColumns() {
        return [
            { data: 'engine', title: '发动机型号', width: 300, readOnly: true },
            {
                data: 'count',
                title: '出现次数',
                width: 120,
                readOnly: true,
                type: 'numeric',
                numericFormat: { pattern: '0' }
            }
        ];
    }

    /**
     * 底盘统计表格列定义
     */
    function buildChassisColumns() {
        return [
            { data: 'chassis', title: '底盘型号', width: 300, readOnly: true },
            {
                data: 'count',
                title: '出现次数',
                width: 120,
                readOnly: true,
                type: 'numeric',
                numericFormat: { pattern: '0' }
            }
        ];
    }

    /**
     * 创建发动机统计表格配置
     * @param {Array} localData 本地数据
     */
    function createEngineConfig(localData) {
        return {
            containerSelector: '#engineStatsGrid',
            pageKey: 'engine_chassis_stats',
            gridKey: 'engine_stats_grid',
            columns: buildEngineColumns(),
            localData: localData || [],
            components: {
                pagination: {
                    pageSizeOptions: [20, 50, 100, 200],
                    defaultPageSize: 50,
                    showScrollToTop: true
                },
                columnMenu: { persist: true },
                doubleClickCopy: true,
                copyToast: true,
                contextMenu: false,
                ellipsisText: true
            }
        };
    }

    /**
     * 创建底盘统计表格配置
     * @param {Array} localData 本地数据
     */
    function createChassisConfig(localData) {
        return {
            containerSelector: '#chassisStatsGrid',
            pageKey: 'engine_chassis_stats',
            gridKey: 'chassis_stats_grid',
            columns: buildChassisColumns(),
            localData: localData || [],
            components: {
                pagination: {
                    pageSizeOptions: [20, 50, 100, 200],
                    defaultPageSize: 50,
                    showScrollToTop: true
                },
                columnMenu: { persist: true },
                doubleClickCopy: true,
                copyToast: true,
                contextMenu: false,
                ellipsisText: true
            }
        };
    }

    return {
        pageKey: 'engine_chassis_stats',
        getDateRange: getDateRange,
        createEngineConfig: createEngineConfig,
        createChassisConfig: createChassisConfig
    };
})();
