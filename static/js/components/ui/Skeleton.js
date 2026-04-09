/**
 * 骨架屏组件
 * 用于数据加载时的占位显示
 */
class Skeleton {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            rows: 10,
            columns: 5,
            rowHeight: 40,
            ...options
        };
        this.element = null;
    }

    /**
     * 显示骨架屏
     */
    show() {
        if (this.element) return;

        this.element = document.createElement('div');
        this.element.className = 'datagrid-skeleton';
        this.element.innerHTML = this.render();

        this.container.appendChild(this.element);
    }

    /**
     * 隐藏骨架屏
     */
    hide() {
        if (this.element) {
            this.element.remove();
            this.element = null;
        }
    }

    /**
     * 渲染骨架屏
     */
    render() {
        const { rows, columns } = this.options;

        let html = '<div class="skeleton-header">';
        for (let i = 0; i < columns; i++) {
            html += `<div class="skeleton-cell" style="flex: ${i === 0 ? 0.5 : 1};"></div>`;
        }
        html += '</div>';

        html += '<div class="skeleton-body">';
        for (let i = 0; i < rows; i++) {
            html += '<div class="skeleton-row">';
            for (let j = 0; j < columns; j++) {
                html += `<div class="skeleton-cell shine" style="flex: ${j === 0 ? 0.5 : 1};"></div>`;
            }
            html += '</div>';
        }
        html += '</div>';

        return html;
    }

    /**
     * 销毁
     */
    destroy() {
        this.hide();
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Skeleton;
}
