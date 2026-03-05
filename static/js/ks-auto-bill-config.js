/**
 * 开思自动开单页面配置文件
 */

const KSAutoBillConfig = {
    // 表格配置
    TABLE: {
        ID: 'ksAutoBillTable',
        HEIGHT: 'full-265',
        PAGE_SIZE: 200,
        PAGE_SIZES: [50, 100, 200]
    },
    
    // API配置
    API: {
        DATA_URL: '/api/ks_auto_bill_data'
    },
    
    // 字段配置
    FIELDS: [
        {type: 'numbers', title: '序号', width: 60},
        {field: 'date', title: '时间', width: 100, sort: true},
        {field: 'ks_order_id', title: '开思订单号', width: 150, sort: true},
        {field: 'crm_order_id', title: 'CRM订单号', width: 180, sort: true},
        {field: 'customer', title: '客户', width: 350, sort: true},
        {field: 'crm_order_link', title: 'CRM订单链接', width: 450}, 
        {field: 'quantity', title: '数量', width: 80, sort: true},
        {field: 'amount', title: '金额', width: 100, sort: true},
        {field: 'execution_log', title: '执行日志', width: 100},
        {field: 'crm_order_status', title: 'CRM订单状态', width: 120}
    ],
    
    // 选择器配置
    SELECTORS: {
        SEARCH_FORM: '#searchForm',
        DATE_RANGE: '#dateRange',
        AUTO_BILLED_TOP_BTN: '#autoBilledTopBtn',
        RESET_BTN: '#resetBtn'
    },
    
    // 功能配置
    FEATURES: {
        ENABLE_COPY: true,
        ENABLE_ADD_TO_CART: false
    }
};