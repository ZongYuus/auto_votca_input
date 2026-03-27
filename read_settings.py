import re

def read_settings(filename):
    """
    读取settings文件（宽容模式），支持：
      - 单值: key : "value"
      - 多值: key : "value1", "value2", "value3"
      - key 只能是字母、数字、下划线
      - 行尾可以有 # 注释
    不合法行会打印提示信息，但不会中止程序。
    返回：
      dict: { key1: value1_or_list, key2: value2_or_list, ... }
    """
    settings = {}
    key_pattern = re.compile(r"^\w+$")  # 允许字母、数字、下划线

    with open(filename, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            original_line = line.rstrip("\n")
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # 忽略空行和整行注释

            # 去掉行尾注释
            if "#" in line:
                line = line.split("#", 1)[0].strip()

            if ":" not in line:
                print(f"Warning: Line {lineno} skipped (missing ':') -> {original_line}")
                continue

            key, values_str = line.split(":", 1)
            key = key.strip()
            values_str = values_str.strip()

            # 检查key是否合法
            if not key_pattern.match(key):
                print(f"Warning: Line {lineno} skipped (invalid key) -> {original_line}")
                continue

            # 分割多个值
            raw_values = [v.strip() for v in values_str.split(",")]
            processed_values = []
            invalid_value_found = False
            for v in raw_values:
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    processed_values.append(v[1:-1])  # 去掉引号
                else:
                    print(f"Warning: Line {lineno} skipped (value not in quotes) -> {original_line}")
                    invalid_value_found = True
                    break  # 整行跳过

            if invalid_value_found:
                continue

            # 如果只有一个值，直接返回字符串；多个值返回列表
            if len(processed_values) == 1:
                settings[key] = processed_values[0]
            else:
                settings[key] = processed_values

    return settings


# ======= 使用示例 =======
# if __name__ == "__main__":
#     settings = read_settings("settings.txt")
#     print("Settings loaded successfully:")
#     print(settings)

    # 示例访问
    # crystal_file = settings.get("crystal")
    # print(f"Crystal file: {crystal_file}")

    # pdb_files = settings.get("single")
    # print(f"Single PDB files: {pdb_files}")