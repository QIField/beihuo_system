def build_tree_by_group(data_list, level_keys, children_key="children"):
    """
    按属性分组聚合生成树形结构
    :param data_list: 字典列表
    :param level_keys: 层级字段顺序 list，如 ["province", "city", "area"]
    :param children_key: 子节点字段名
    :return: list
    """
    root = []
    for row in data_list:
        current = root
        for idx, key in enumerate(level_keys):
            val = row[key]
            # 查找同层级相同属性节点
            target = None
            for node in current:
                if node.get(key) == val:
                    target = node
                    break
            if not target:
                target = {key: val}
                # 非最后一层创建children容器
                if idx != len(level_keys) - 1:
                    target[children_key] = []
                current.append(target)
            # 最后一层不再向下走
            if idx != len(level_keys) - 1:
                current = target[children_key]
    return root


# 测试示例
if __name__ == "__main__":
    data = [
        {"province":"广东", "city":"佛山", "area":"禅城"},
        {"province":"广东", "city":"佛山", "area":"南海"},
        {"province":"广东", "city":"广州", "area":"天河"},
        {"province":"广西", "city":"南宁", "area":"青秀"},
    ]
    tree = build_tree_by_group(data, ["province", "city", "area"])
    import json
    print(json.dumps(tree, ensure_ascii=False, indent=2))