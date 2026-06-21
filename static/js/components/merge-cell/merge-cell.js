/**
 * AG Grid 合并单元格辅助组件
 * 用于按某个字段分组，将指定列跨行合并显示
 */
const MergeCellHelper = (function() {
    'use strict';

    /**
     * 按指定字段对行数据连续分组，并打上合并标记
     * @param {Array} rows 行数据
     * @param {string} groupField 分组字段，如 'inquiryId'
     * @param {Object} options 配置项
     * @param {string} options.indexField 序号字段名，默认 '_groupIndex'
     * @param {string} options.spanField 跨行数字段名，默认 '_rowSpan'
     */
    function computeRowSpans(rows, groupField, options) {
        if (!rows || rows.length === 0) return;

        options = options || {};
        const indexField = options.indexField || '_groupIndex';
        const spanField = options.spanField || '_rowSpan';

        let i = 0;
        let groupCount = 0;
        let groupIndex = 0;

        while (i < rows.length) {
            const currentKey = rows[i][groupField];
            let j = i + 1;
            while (j < rows.length && rows[j][groupField] === currentKey) {
                j++;
            }
            groupIndex++;
            const span = j - i;

            if (span > 1) {
                rows[i][spanField] = span;
                rows[i]._isMergeStart = true;
                rows[i][indexField] = groupIndex;
                for (let k = i + 1; k < j; k++) {
                    rows[k][spanField] = 1;
                    rows[k]._isMerged = true;
                    rows[k][indexField] = groupIndex;
                }
                rows[j - 1]._isGroupEnd = true;
                groupCount++;
            } else {
                rows[i][spanField] = 1;
                rows[i]._isMerged = false;
                rows[i][indexField] = groupIndex;
                rows[i]._isGroupEnd = true;
            }
            i = j;
        }

        console.log(`[MergeCellHelper] 分组字段: ${groupField}, 多行组: ${groupCount}, 总行数: ${rows.length}, 总组数: ${groupIndex}`);
    }

    /**
     * 给列定义批量添加 rowSpan 和 merged-cell class
     * @param {Array} columnDefs AG Grid 列定义
     * @param {Array} mergeFields 需要合并的字段名列表
     * @param {Object} options 配置项
     * @param {Array} options.wrapTextFields 需要自动换行的字段
     * @param {Array} options.leftFields 左侧固定列字段
     */
    function applyMergeColumns(columnDefs, mergeFields, options) {
        options = options || {};
        const wrapTextFields = options.wrapTextFields || [];
        const leftFields = options.leftFields || [];

        return columnDefs.map(function(col) {
            if (!mergeFields.includes(col.field)) {
                return col;
            }

            const extraClasses = [];
            if (leftFields.includes(col.field)) {
                extraClasses.push('col-left');
            }
            if (wrapTextFields.includes(col.field)) {
                extraClasses.push('wrap-text');
            }

            return Object.assign({}, col, {
                rowSpan: function(params) {
                    return (params.data && params.data._rowSpan) ? params.data._rowSpan : 1;
                },
                cellClassRules: Object.assign({}, col.cellClassRules || {}, {
                    'merged-cell': function(params) {
                        return params.data && params.data._rowSpan >= 1;
                    }
                }),
                cellClass: function(params) {
                    if (extraClasses.length === 0) return col.cellClass || '';
                    const extraClassStr = extraClasses.join(' ');
                    if (typeof col.cellClass === 'function') {
                        return ((col.cellClass(params) || '') + ' ' + extraClassStr).trim();
                    }
                    return ((col.cellClass || '') + ' ' + extraClassStr).trim();
                }
            });
        });
    }

    /**
     * 生成一个按组合并的「行号」列定义
     * @param {Object} options
     * @param {string} options.headerName 默认 '行号'
     * @param {number} options.width 默认 80
     * @param {string} options.indexField 默认 '_groupIndex'
     */
    function createRowNumberColumn(options) {
        options = options || {};
        return {
            headerName: options.headerName || '行号',
            field: options.field || 'rowNumber',
            width: options.width || 80,
            pinned: options.pinned || 'left',
            sortable: false,
            filter: false,
            rowSpan: function(params) {
                return (params.data && params.data._rowSpan) ? params.data._rowSpan : 1;
            },
            cellClassRules: {
                'merged-cell': function(params) {
                    return params.data && params.data._rowSpan >= 1;
                }
            },
            cellClass: 'col-left',
            valueGetter: function(params) {
                return params.data ? params.data[options.indexField || '_groupIndex'] : '';
            }
        };
    }

    /**
     * 获取合并单元格必需的 gridOptions 配置
     */
    function getGridOptions() {
        return {
            suppressRowTransform: true,   // 官方 rowSpan 必需
            rowBuffer: 30,                // 减少滚动时合并失效
            animateRows: false            // 避免与合并块冲突
        };
    }

    /**
     * 一条龙：打标 + 设置数据
     * @param {Object} gridApi AG Grid api
     * @param {Array} rows 数据
     * @param {string} groupField 分组字段
     */
    function setRowDataWithMerge(gridApi, rows, groupField) {
        computeRowSpans(rows, groupField);
        gridApi.setRowData(rows);
    }

    return {
        computeRowSpans: computeRowSpans,
        applyMergeColumns: applyMergeColumns,
        createRowNumberColumn: createRowNumberColumn,
        getGridOptions: getGridOptions,
        setRowDataWithMerge: setRowDataWithMerge
    };
})();
