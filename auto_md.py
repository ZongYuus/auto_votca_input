import os
import sys
import shutil
import subprocess
from read_settings import read_settings

def get_resource_dir(folder_name):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, folder_name)

def prepare_workdir(settings):
    """
    创建工作目录 MD_TEMP，并将 crystal 文件从 MOL_FILES 复制进去
    """
    # 检查 settings 中是否提供 crystal
    if "crystal" not in settings:
        raise ValueError("Missing 'crystal' in settings")

    source_dir = "MOL_FILES"   # 原始 pdb 文件所在目录
    workdir = "MD_TEMP"        # 工作目录（所有计算在这里进行）

    # 创建工作目录（已存在不会报错）
    os.makedirs(workdir, exist_ok=True)

    crystal_file = settings["crystal"]

    # 拼接源文件路径：MOL_FILES/cry.pdb
    src = os.path.join(source_dir, crystal_file)

    # 检查文件是否存在
    if not os.path.exists(src):
        raise FileNotFoundError(f"{src} not found")

    # 目标路径：MD_TEMP/cry.pdb
    dest = os.path.join(workdir, crystal_file)

    # 复制文件到工作目录
    shutil.copy(src, dest)

    print(f"Copied: {src} -> {dest}")

    return workdir


def build_supercell(settings, workdir):
    """
    使用 gmx genconf 构建 supercell
    """
    # 检查是否提供 supercell 参数
    if "supercell" not in settings:
        raise ValueError("Missing 'supercell' in settings")

    supercell = settings["supercell"]

    # 必须是3个数
    if not isinstance(supercell, list) or len(supercell) != 3:
        raise ValueError("'supercell' must contain exactly 3 values")

    # 转换为整数 a b c
    a, b, c = map(int, supercell)

    crystal_file = settings["crystal"]

    # 输出文件名：.gro
    output_file = crystal_file.replace(".pdb", ".gro")

    # 构建 gmx 命令
    cmd = [
        "gmx", "genconf",
        "-f", crystal_file,
        "-o", output_file,
        "-nbox", str(a), str(b), str(c)
    ]

    print("Running:", " ".join(cmd))

    # 在 MD_TEMP 目录中执行命令
    subprocess.run(cmd, cwd=workdir, check=True)


def run_mdp_pipeline(settings):
    """
    通用 MD pipeline：
    - 从 MDP_DEFAULT 复制 mdp 到 MD_TEMP
    - 在 MD_TEMP 中执行 grompp + mdrun
    - 自动串联 gro 文件
    """
    crystal_file = settings["crystal"]
    output_file = crystal_file.replace(".pdb", ".gro")
    top_file = crystal_file.replace(".pdb", ".top")

    mdp_default_dir = get_resource_dir("MDP_DEFAULT")
    workdir = "MD_TEMP"   

    # ====== 1. 获取 mdp 列表 ======
    if "mdp" not in settings or settings["mdp"] == "default":
        mdp_list = ["min.mdp", "nvt.mdp"]
    else:
        mdp_list = settings["mdp"]
        if isinstance(mdp_list, str):
            mdp_list = [mdp_list]

    print("Using MDP files:", mdp_list)

    # ====== 2. 拷贝 mdp 文件到 MD_TEMP ======
    for mdp in mdp_list:
        src = os.path.join(mdp_default_dir, mdp)
        dst = os.path.join(workdir, mdp)

        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} not found")

        shutil.copy(src, dst)
        print(f"Copied: {src} -> {dst}")

    # ====== 3. 逐步执行 ======
    prev_gro = output_file   # 初始结构（已在 MD_TEMP 中）

    for mdp in mdp_list:
        name = os.path.splitext(mdp)[0]

        # grompp
        grompp_cmd = [
            "gmx", "grompp",
            "-f", mdp,
            "-p", top_file,
            "-c", prev_gro,
            "-o", f"{name}.tpr",
            "-maxwarn", "4"
        ]

        print("Running:", " ".join(grompp_cmd))
        subprocess.run(grompp_cmd, cwd=workdir, check=True)

        # mdrun
        mdrun_cmd = [
            "gmx", "mdrun",
            "-v",
            "-deffnm", name
        ]

        print("Running:", " ".join(mdrun_cmd))
        subprocess.run(mdrun_cmd, cwd=workdir, check=True)

        # 下一步输入
        prev_gro = f"{name}.gro"

# def main():
#     """
#     主流程：
#     1. 读取 settings
#     2. 准备工作目录
#     3. 构建 supercell
#     """
#     settings = read_settings("settings.txt")

#     # Step 1: 准备 MD_TEMP 并复制输入文件
#     workdir = prepare_workdir(settings)

#     # Step 2: 执行 gmx genconf
#     build_supercell(settings, workdir)

#     # Step 3: 跑md
#     run_mdp_pipeline(settings)

# if __name__ == "__main__":
#     main()