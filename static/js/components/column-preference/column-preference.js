/**
 * Column Preference Component
 * 表格列状态持久化组件
 *
 * 功能：
 *  1. 页面加载时从后端读取用户的列状态（列宽/列顺序/显隐）
 *  2. 自动调用 columnApi.applyColumnState 恢复列展示
 *  3. 监听 AG Grid 列变化事件（columnVisible / columnMoved / columnResized）
 *  4. 防抖保存到后端，按 user_id + page_key + grid_key 唯一关联
 *
 * Usage:
 *   ColumnPreference.init(gridApi, {
 *       columnApi: gridColumnApi,   // 必填
 *       pageKey: 'ks_inquiry_records',
 *       gridKey: 'detail_grid',
 *       debounceMs: 600,            // 可选，默认 600ms
 *       onApplied: function(state) {} // 可选，列状态恢复完成回调
 *   });
 *
 * 后端接口：
 *   GET  /new/api/column_preference?page_key=xxx&grid_key=xxx
 *   POST /new/api/column_preference   body: {page_key, grid_key, column_state}
 */

var ColumnPreference = (function() {
    'use strict';

    var API_BASE = '/new/api/column_preference';
    var registry = {}; // gridKey => { config, saveTimer }

    function _key(pageKey, gridKey) {
        return pageKey + '::' + gridKey;
    }

    /**
     * 初始化：加载并恢复用户列状态，绑定变化事件自动保存
     * @param {Object} gridApi - AG Grid API
     * @param {Object} options - { columnApi, pageKey, gridKey, debounceMs, onApplied }
     */
    function init(gridApi, options) {
        if (!gridApi) {
            console.warn('[ColumnPreference] gridApi 必填');
            return;
        }
        options = options || {};
        var columnApi = options.columnApi || (gridApi && gridApi.columnApi) || null;
        var pageKey = options.pageKey;
        var gridKey = options.gridKey;
        var debounceMs = typeof options.debounceMs === 'number' ? options.debounceMs : 600;

        if (!pageKey || !gridKey) {
            console.warn('[ColumnPreference] pageKey 与 gridKey 必填');
            return;
        }

        var entry = {
            gridApi: gridApi,
            columnApi: columnApi,
            pageKey: pageKey,
            gridKey: gridKey,
            debounceMs: debounceMs,
            onApplied: options.onApplied || null,
            saveTimer: null,
            applying: false  // 恢复列状态时不触发保存
        };
        registry[_key(pageKey, gridKey)] = entry;

        // 1. 加载用户配置 → 恢复列状态
        _loadAndApply(entry);

        // 2. 绑定列变化事件 → 防抖保存
        _bindEvents(entry);
    }

    function _loadAndApply(entry) {
        var url = API_BASE + '?page_key=' + encodeURIComponent(entry.pageKey) +
                  '&grid_key=' + encodeURIComponent(entry.gridKey);
        fetch(url, { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(resp) {
                if (!resp || resp.code !== 0) return;
                var state = resp.data;
                if (!state || !Array.isArray(state) || state.length === 0) return;

                // 过滤掉 sort/sortIndex 字段：列状态只持久化"宽/顺序/显隐"，
                // 排序状态由 GridColumnMenu 单独管理，避免恢复时影响排序逻辑
                state = state.map(function(s) {
                    var clone = Object.assign({}, s);
                    delete clone.sort;
                    delete clone.sortIndex;
                    return clone;
                });

                var api = entry.columnApi || entry.gridApi;
                entry.applying = true;
                try {
                    if (typeof api.applyColumnState === 'function') {
                        api.applyColumnState({ state: state, applyOrder: true });
                    } else if (typeof api.setColumnState === 'function') {
                        api.setColumnState(state);
                    }
                    if (typeof entry.onApplied === 'function') {
                        try { entry.onApplied(state); } catch (e) {}
                    }
                } catch (e) {
                    console.warn('[ColumnPreference] applyColumnState error:', e.message);
                }
                // 下一帧再放开保存监听，避免恢复立即触发保存
                setTimeout(function() { entry.applying = false; }, 50);
            })
            .catch(function(err) {
                console.warn('[ColumnPreference] load error:', err);
            });
    }

    function _bindEvents(entry) {
        var api = entry.gridApi;
        if (!api || typeof api.addEventListener !== 'function') return;

        var handler = function() {
            if (entry.applying) return;
            _scheduleSave(entry);
        };
        api.addEventListener('columnVisible', handler);
        api.addEventListener('columnMoved', handler);
        api.addEventListener('columnResized', handler);
        api.addEventListener('columnPinned', handler);
    }

    function _scheduleSave(entry) {
        if (entry.saveTimer) clearTimeout(entry.saveTimer);
        entry.saveTimer = setTimeout(function() {
            _save(entry);
        }, entry.debounceMs);
    }

    function _save(entry) {
        var api = entry.columnApi || entry.gridApi;
        var state = null;
        try {
            if (typeof api.getColumnState === 'function') {
                state = api.getColumnState();
            }
        } catch (e) {
            console.warn('[ColumnPreference] getColumnState error:', e.message);
        }
        if (!state) return;

        // 保存时去掉 sort/sortIndex 字段：排序状态不在持久化范围内
        state = state.map(function(s) {
            var clone = Object.assign({}, s);
            delete clone.sort;
            delete clone.sortIndex;
            return clone;
        });

        fetch(API_BASE, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                page_key: entry.pageKey,
                grid_key: entry.gridKey,
                column_state: state
            })
        }).catch(function(err) {
            console.warn('[ColumnPreference] save error:', err);
        });
    }

    /**
     * 手动触发保存（外部组件改变列显隐后可调用）
     */
    function flush(pageKey, gridKey) {
        var entry = registry[_key(pageKey, gridKey)];
        if (!entry) return;
        if (entry.saveTimer) clearTimeout(entry.saveTimer);
        _save(entry);
    }

    /**
     * 重置：删除后端配置
     */
    function reset(pageKey, gridKey) {
        var url = API_BASE + '?page_key=' + encodeURIComponent(pageKey) +
                  '&grid_key=' + encodeURIComponent(gridKey);
        return fetch(url, { method: 'DELETE', credentials: 'same-origin' });
    }

    return {
        init: init,
        flush: flush,
        reset: reset
    };
})();
