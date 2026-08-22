/**
 * 性能监控工具
 * 用于统计业务数据加载流程中各关键步骤的耗时，与业务逻辑解耦。
 */
class PerformanceMonitor {
    constructor(label) {
        this.label = label || '性能监控';
        this.steps = [];
        this.startTime = performance.now();
        this.lastTime = this.startTime;
    }

    /**
     * 记录一个关键步骤的完成时间点。
     * @param {string} stepName - 步骤名称
     */
    mark(stepName) {
        const now = performance.now();
        this.steps.push({
            name: stepName,
            duration: now - this.lastTime,
            timestamp: now
        });
        this.lastTime = now;
    }

    /**
     * 完成监控并一次性汇总打印所有步骤耗时。
     */
    finish() {
        const total = performance.now() - this.startTime;
        const lines = this.steps.map((step, index) => {
            return `  ${index + 1}. ${step.name}: ${step.duration.toFixed(2)} ms`;
        });

        console.log(
            `[${this.label}] 数据加载性能统计\n` +
            lines.join('\n') +
            `\n  总耗时: ${total.toFixed(2)} ms`
        );
    }
}
