/**
 * GridDetailPanel 组件
 * 主表点击某行后，在指定位置展开副表面板展示详情数据
 * 支持位置：bottom / top / left / right
 * 支持拖拽调整面板大小
 *
 * 使用示例：
 * var detailPanel = GridDetailPanel.init({
 *     containerSelector: '#tab-oe',
 *     masterGridSelector: '#oeStatsGrid',
 *     masterGridApi: oeStatsGridApi,
 *     position: 'bottom',
 *     title: 'OE号询价明细',
 *     columnDefs: [...],
 *     loadUrl: '/new/api/ks_inquiry/records',
 *     buildParams: function(rowData) { return { parts_num: rowData.partsNum }; }
 * });
 *
 * // 在主表 onRowClicked 中调用
 * detailPanel.open(event.data);
 */
(function(global) {
    'use strict';

    class GridDetailPanel {
        constructor(options) {
            this.options = Object.assign({
                containerSelector: '',
                masterGridSelector: '',
                masterGridApi: null,
                position: 'bottom',
                title: '详情',
                gridId: null,
                columnDefs: [],
                defaultColDef: {},
                loadUrl: '',
                buildParams: null,
                splitRatio: 0.4,
                pageSizeOptions: [20, 50, 100],
                defaultPageSize: 50,
                persistPageKey: 'ks_inquiry_records',
                persistGridKey: null,
                rowKeyField: null,
                showPagination: true,
                getRowClass: null,
                onBeforeLoad: null,
                onLoad: null,
                onClose: null
            }, options);

            this.container = null;
            this.masterWrapper = null;
            this.detailWrapper = null;
            this.resizer = null;
            this.gridId = null;

            this.detailGridApi = null;
            this.detailGridColumnApi = null;
            this.detailGridLoader = null;
            this.detailPagination = null;

            this.isOpen = false;
            this.currentRowData = null;
            this.currentPage = 1;
            this.currentPageSize = this.options.defaultPageSize;
            this.totalRecords = 0;
            this.currentDetailSize = null;

            this.init();
        }

        init() {
            this.container = document.querySelector(this.options.containerSelector);
            if (!this.container) {
                console.error('[GridDetailPanel] 容器不存在:', this.options.containerSelector);
                return;
            }

            this.setupLayout();
        }

        setupLayout() {
            const masterGridEl = document.querySelector(this.options.masterGridSelector);
            const masterParent = masterGridEl ? masterGridEl.parentNode : null;

            const wrapper = document.createElement('div');
            wrapper.className = 'grid-detail-panel-wrapper';

            const isHorizontal = this.options.position === 'left' || this.options.position === 'right';
            wrapper.style.flexDirection = isHorizontal ? 'row' : 'column';

            this.masterWrapper = document.createElement('div');
            this.masterWrapper.className = 'grid-detail-master-wrapper';
            if (masterParent) {
                this.masterWrapper.appendChild(masterParent);
            }

            this.resizer = document.createElement('div');
            this.resizer.className = 'grid-detail-resizer ' + (isHorizontal ? 'horizontal' : 'vertical');

            this.detailWrapper = document.createElement('div');
            this.detailWrapper.className = 'grid-detail-detail-wrapper';
            this.detailWrapper.style.display = 'none';

            const header = document.createElement('div');
            header.className = 'grid-detail-header';
            header.innerHTML = '<span class="grid-detail-title">' + this.options.title + '</span>' +
                               '<button class="grid-detail-close" title="关闭">&times;</button>';

            this.gridId = this.options.gridId || ('detailGrid_' + Date.now());
            const gridDiv = document.createElement('div');
            gridDiv.id = this.gridId;
            gridDiv.className = 'ag-theme-alpine grid-detail-grid';

            this.detailWrapper.appendChild(header);
            this.detailWrapper.appendChild(gridDiv);

            if (this.options.showPagination) {
                const paginationDiv = document.createElement('div');
                paginationDiv.id = this.gridId + '_pagination';
                paginationDiv.className = 'grid-detail-pagination';
                this.detailWrapper.appendChild(paginationDiv);
            }

            if (this.options.position === 'bottom' || this.options.position === 'right') {
                wrapper.appendChild(this.masterWrapper);
                wrapper.appendChild(this.resizer);
                wrapper.appendChild(this.detailWrapper);
            } else {
                wrapper.appendChild(this.detailWrapper);
                wrapper.appendChild(this.resizer);
                wrapper.appendChild(this.masterWrapper);
            }

            this.container.appendChild(wrapper);

            header.querySelector('.grid-detail-close').addEventListener('click', () => {
                this.close();
            });

            this.bindResizerEvents();
            this.initDetailGrid(gridDiv);
        }

        initDetailGrid(gridDiv) {
            var self = this;
            var gridId = this.gridId;

            var gridOptions = {
                columnDefs: this.options.columnDefs,
                rowData: [],
                defaultColDef: Object.assign({
                    sortable: false,
                    filter: true,
                    resizable: true,
                    suppressMenu: true
                }, this.options.defaultColDef),
                rowHeight: 36,
                headerHeight: 36,
                pagination: false,
                animateRows: true,
                overlayLoadingTemplate: '<span class="ag-overlay-loading-center">正在加载数据...</span>',
                overlayNoRowsTemplate: '<span class="ag-overlay-no-rows-center">暂无数据</span>',
                getRowClass: this.options.getRowClass || null,
                onGridReady: function(event) {
                    self.detailGridApi = event.api;
                    self.detailGridColumnApi = event.columnApi;
                    self.detailGridLoader = new AgGridLoader(self.detailGridApi);

                    if (typeof GridColumnMenu !== 'undefined') {
                        var menuOptions = {
                            columnApi: self.detailGridColumnApi,
                            gridOptions: gridOptions,
                            persist: true,
                            pageKey: self.options.persistPageKey,
                            gridKey: self.options.persistGridKey || gridId,
                            onSort: function() {
                                self.loadDetailData(1, self.currentPageSize);
                            },
                            onDataRefresh: function() {
                                self.loadDetailData(1, self.currentPageSize);
                            }
                        };
                        if (typeof self.options.getFilterValues === 'function') {
                            menuOptions.getFilterValues = function(colId, callback) {
                                self.options.getFilterValues(colId, callback, self.currentRowData);
                            };
                        }
                        GridColumnMenu.init(self.detailGridApi, '#' + gridId, self.options.columnDefs, menuOptions);
                    }

                    self.detailGridApi.sizeColumnsToFit();
                }
            };

            new agGrid.Grid(gridDiv, gridOptions);

            if (this.options.showPagination && typeof CustomPagination !== 'undefined') {
                this.detailPagination = CustomPagination.init({
                    container: '#' + gridId + '_pagination',
                    gridSelector: '#' + gridId,
                    pageSizeOptions: [50, 100, 200, 500],
                    defaultPageSize: 200,
                    showScrollToTop: true,
                    onPageChange: function(page, pageSize) {
                        self.currentPage = page;
                        self.currentPageSize = pageSize;
                        self.loadDetailData(page, pageSize);
                    },
                    onPageSizeChange: function(pageSize) {
                        self.currentPageSize = pageSize;
                    }
                });
            }
        }

        bindResizerEvents() {
            var self = this;
            var isResizing = false;
            var startPos = 0;
            var startSize = 0;
            var isHorizontal = this.options.position === 'left' || this.options.position === 'right';

            function getPos(e) {
                return isHorizontal ? e.clientX : e.clientY;
            }

            function getSize() {
                return isHorizontal ? self.detailWrapper.offsetWidth : self.detailWrapper.offsetHeight;
            }

            function setSize(size) {
                if (isHorizontal) {
                    self.detailWrapper.style.width = size + 'px';
                } else {
                    self.detailWrapper.style.height = size + 'px';
                }
                self.detailWrapper.style.flex = 'none';
                self.masterWrapper.style.flex = '1';
                self.currentDetailSize = size;
            }

            this.resizer.addEventListener('mousedown', function(e) {
                isResizing = true;
                startPos = getPos(e);
                startSize = getSize();
                document.body.style.cursor = isHorizontal ? 'col-resize' : 'row-resize';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            });

            function onMouseMove(e) {
                if (!isResizing) return;
                var delta = getPos(e) - startPos;
                var direction = (self.options.position === 'right' || self.options.position === 'bottom') ? -1 : 1;
                var newSize = startSize + delta * direction;
                var wrapperSize = isHorizontal ? self.container.clientWidth : self.container.clientHeight;
                var minSize = 150;
                var maxSize = wrapperSize - minSize;
                setSize(Math.max(minSize, Math.min(maxSize, newSize)));
            }

            function onMouseUp() {
                if (!isResizing) return;
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        }

        open(rowData) {
            var self = this;
            var keyField = this.options.rowKeyField ||
                           (this.options.columnDefs[0] && this.options.columnDefs[0].field) || 'id';
            this.currentRowData = rowData;
            this.isOpen = true;
            this.currentPage = 1;

            if (this.options.masterGridApi) {
                this.options.masterGridApi.forEachNode(function(node) {
                    node.setSelected(false);
                });
                var targetNode = null;
                this.options.masterGridApi.forEachNode(function(node) {
                    if (node.data[keyField] === rowData[keyField]) {
                        targetNode = node;
                    }
                });
                if (targetNode) {
                    targetNode.setSelected(true);
                }
            }

            this.detailWrapper.style.display = 'flex';
            var isHorizontal = this.options.position === 'left' || this.options.position === 'right';
            var size = this.currentDetailSize;
            if (!size) {
                var wrapperSize = isHorizontal ? this.container.clientWidth : this.container.clientHeight;
                size = Math.max(150, Math.min(wrapperSize - 150, wrapperSize * this.options.splitRatio));
            }
            if (isHorizontal) {
                this.detailWrapper.style.width = size + 'px';
            } else {
                this.detailWrapper.style.height = size + 'px';
            }
            this.detailWrapper.style.flex = 'none';
            this.masterWrapper.style.flex = '1';

            if (this.detailGridApi) {
                setTimeout(function() {
                    self.detailGridApi.sizeColumnsToFit();
                    if (typeof GridColumnMenu !== 'undefined' && GridColumnMenu.addMenuButtonsToHeaders) {
                        GridColumnMenu.addMenuButtonsToHeaders('#' + self.gridId);
                    }
                }, 0);
            }

            if (this.options.onBeforeLoad) {
                this.options.onBeforeLoad(rowData);
            }

            this.loadDetailData(1, this.currentPageSize);
        }

        close() {
            this.isOpen = false;
            this.currentRowData = null;
            this.detailWrapper.style.display = 'none';
            this.masterWrapper.style.flex = '1';

            if (this.options.masterGridApi) {
                this.options.masterGridApi.forEachNode(function(node) {
                    node.setSelected(false);
                });
            }

            if (this.options.onClose) {
                this.options.onClose();
            }
        }

        loadDetailData(page, pageSize) {
            var self = this;
            if (!this.currentRowData || !this.options.loadUrl) return;

            var params = this.options.buildParams ? this.options.buildParams(this.currentRowData) : {};
            if (this.options.showPagination) {
                params.page = page;
                params.page_size = pageSize;
            }

            // 副表列头排序/筛选状态透传到后端
            if (typeof GridColumnMenu !== 'undefined') {
                var sortState = GridColumnMenu.getSortState('#' + self.gridId);
                if (sortState.sortColumn) {
                    params.sort_column = sortState.sortColumn;
                    params.sort_dir = sortState.sortDir;
                }
                var filterState = GridColumnMenu.getFilterState('#' + self.gridId);
                if (filterState.active && filterState.filters) {
                    params.column_filters = JSON.stringify(filterState.filters);
                }
            }

            if (this.detailGridLoader) {
                this.detailGridLoader.load(this.options.loadUrl, params, function(data) {
                    self.totalRecords = data.total || 0;
                    if (self.detailPagination) {
                        self.detailPagination.update(self.totalRecords, page, pageSize);
                    }

                    // 数据加载完成后，缓存原始行并刷新列菜单按钮（防止副表初始隐藏时按钮未挂上）
                    var list = data.list || [];
                    if (typeof GridColumnMenu !== 'undefined') {
                        GridColumnMenu.setOriginalRows('#' + self.gridId, list);
                        setTimeout(function() {
                            GridColumnMenu.addMenuButtonsToHeaders('#' + self.gridId);
                        }, 50);
                    }

                    if (self.options.onLoad) {
                        self.options.onLoad(data);
                    }
                }, function(error) {
                    console.error('[GridDetailPanel] 加载失败:', error);
                });
            }
        }
    }

    GridDetailPanel.init = function(options) {
        return new GridDetailPanel(options);
    };

    global.GridDetailPanel = GridDetailPanel;
})(window);
