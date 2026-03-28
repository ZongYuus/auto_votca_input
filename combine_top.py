# combine_top.py

import os
import shutil
from read_settings import read_settings

TOP_DIR = "TOP"
MD_TEMP_DIR = "MD_TEMP"


def extract_itp_content(top_file):
    """
    从 .top 文件中提取需要保留的部分：
    - 删除 [ defaults ] 段
    - 删除 [ system ] 和 [ molecules ] 段
    """
    with open(top_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip = False

    for line in lines:
        stripped = line.strip()

        # 跳过 [ defaults ]
        if stripped.startswith("[ defaults ]"):
            skip = True
            continue

        # 遇到下一个 section，停止跳过
        if skip and stripped.startswith("[") and not stripped.startswith("[ defaults ]"):
            skip = False

        if skip:
            continue

        # 删除 [ system ] 及之后所有内容
        if stripped.startswith("[ system ]"):
            break

        new_lines.append(line)

    return new_lines


def get_molecule_name_from_itp(itp_path):
    """
    从 .itp 文件中读取 [ moleculetype ] 下的分子名
    """
    with open(itp_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[ moleculetype ]"):
            in_section = True
            continue

        if in_section:
            # 跳过注释和空行
            if not stripped or stripped.startswith(";"):
                continue

            parts = stripped.split()
            return parts[0]  # 分子名

    return None


def process_top():
    """
    - 仅处理 TOP 目录（不递归子目录）
    - 转换为 .itp
    - 拷贝到 MD_TEMP
    - 返回 itp 文件列表
    """
    os.makedirs(MD_TEMP_DIR, exist_ok=True)

    itp_files = []

    for file in os.listdir(TOP_DIR):
        top_path = os.path.join(TOP_DIR, file)

        # 只处理文件
        if not os.path.isfile(top_path):
            continue

        if file.endswith(".top"):
            base_name = os.path.splitext(file)[0]
            itp_name = base_name + ".itp"
            itp_path = os.path.join(TOP_DIR, itp_name)

            # 提取内容
            content = extract_itp_content(top_path)

            # 写入 itp
            with open(itp_path, "w", encoding="utf-8") as f:
                f.writelines(content)

            print(f"Generated ITP: {itp_path}")

            # 拷贝到 MD_TEMP
            dest_path = os.path.join(MD_TEMP_DIR, itp_name)
            shutil.copy(itp_path, dest_path)

            itp_files.append(itp_name)

    return itp_files


def generate_final_top(itp_files):
    """
    生成最终 cry.top：
    - 使用 moleculetype 名
    - 使用 settings 中的 number 和 supercell
    """
    settings = read_settings("settings.txt")

    # number
    number = int(settings.get("number", 1))

    # supercell
    supercell = settings.get("supercell", ["1", "1", "1"])
    supercell = [int(x) for x in supercell]

    # 计算总倍数
    total_multiplier = number
    for x in supercell:
        total_multiplier *= x

    crystal_file = settings["crystal"]
    top_file = crystal_file.replace(".pdb", ".top")
    final_top_path = os.path.join(MD_TEMP_DIR, top_file)

    with open(final_top_path, "w", encoding="utf-8") as f:
        # header
        f.write("; Created by auto pipeline\n\n")

        # defaults
        f.write("[ defaults ]\n")
        f.write("; nbfunc        comb-rule       gen-pairs       fudgeLJ    fudgeQQ\n")
        f.write("     1              2              yes            0.5       0.8333\n\n")

        # include
        for itp in itp_files:
            f.write(f'#include "{itp}"\n')

        f.write("\n")

        # system
        f.write("[ system ]\n")
        f.write("CRY\n\n")

        # molecules
        f.write("[ molecules ]\n")
        f.write("; Molecule      nmols\n")

        for itp in itp_files:
            itp_path = os.path.join(MD_TEMP_DIR, itp)

            mol_name = get_molecule_name_from_itp(itp_path)

            if mol_name is None:
                print(f"Warning: Cannot find moleculetype in {itp}")
                continue

            f.write(f"{mol_name}      {total_multiplier}\n")

    print(f"Final topology generated: {final_top_path}")


# def main():
#     itp_files = process_top()
#     generate_final_top(itp_files)


# if __name__ == "__main__":
#     main()