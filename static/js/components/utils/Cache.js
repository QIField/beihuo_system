/**
 * LRU缓存实现
 * 用于数据缓存，减少重复请求
 */
class LRUCache {
    constructor(maxSize = 50) {
        this.cache = new Map();
        this.maxSize = maxSize;
    }

    /**
     * 获取缓存数据
     * @param {string} key - 缓存键
     * @returns {any} 缓存数据或null
     */
    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;

        // 检查是否过期
        if (Date.now() - item.time > item.ttl) {
            this.cache.delete(key);
            return null;
        }

        // 移到末尾（最近使用）
        this.cache.delete(key);
        this.cache.set(key, item);

        return item.data;
    }

    /**
     * 设置缓存数据
     * @param {string} key - 缓存键
     * @param {any} data - 缓存数据
     * @param {number} ttl - 过期时间(ms)，默认5分钟
     */
    set(key, data, ttl = 300000) {
        // 如果已满，删除最旧的
        if (this.cache.size >= this.maxSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }

        this.cache.set(key, {
            data,
            time: Date.now(),
            ttl
        });
    }

    /**
     * 删除缓存
     * @param {string} key - 缓存键
     */
    delete(key) {
        this.cache.delete(key);
    }

    /**
     * 清空缓存
     */
    clear() {
        this.cache.clear();
    }

    /**
     * 获取缓存大小
     * @returns {number}
     */
    size() {
        return this.cache.size;
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LRUCache;
}
