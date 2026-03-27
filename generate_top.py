# generate_top.py
import os
import shutil
import subprocess
from read_settings import read_settings
from Bio.PDB import PDBParser
global residue_name
# 文件夹设置
MOL_DIR = "MOL_FILES"
TOP_DIR = "TOP"

os.makedirs(MOL_DIR, exist_ok=True)
os.makedirs(TOP_DIR, exist_ok=True)

def get_residue_name_from_pdb(pdb_file):
    """
    使用 BioPython 解析 PDB 文件，提取第一个残基名。
    对于小分子 PDB，HETATM 也视为有效残基。
    """
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure('structure', pdb_file)
    for model in structure:
        for chain in model:
            for residue in chain:
                return residue.get_resname()
    raise ValueError(f"No residue found in {pdb_file}")

def generate_tleap_for_single(single_name):
    global residue_name
    """
    根据 single_name 生成 tleap.in 文件
    single_name: 不带后缀的基础名称，例如 'single1'
    """
    pdb_path = os.path.join(MOL_DIR, single_name + ".pdb")
    mol2_path = os.path.join(MOL_DIR, single_name + ".mol2")

    # 检查 MOL2 文件是否存在
    if not os.path.exists(mol2_path):
        print(f"Warning: MOL2 file '{mol2_path}' not found, skipping.")
        return None

    # 获取残基名
    if os.path.exists(pdb_path):
        try:
            residue_name = get_residue_name_from_pdb(pdb_path)
        except ValueError as e:
            print(f"Error: {e}, using '{single_name.upper()}' as residue name.")
            residue_name = single_name.upper()
    else:
        residue_name = single_name.upper()

    tleap_content = f"""source leaprc.gaff
{residue_name}=loadmol2 {single_name}.mol2
loadamberparams {single_name}.frcmod
saveamberparm {residue_name} {single_name}.prmtop {single_name}.rst7
saveamberparm {residue_name} {single_name}.prmtop {single_name}.inpcrd
savepdb {residue_name} {single_name}_tleap.pdb
quit
"""
    tleap_path = os.path.join(TOP_DIR, f"{single_name}_tleap.in")
    with open(tleap_path, "w", encoding="utf-8") as f:
        f.write(tleap_content)
    print(f"TLeap input generated: {tleap_path}")
    return tleap_path, mol2_path

def run_command(cmd_list, work_dir=None, stdin_file=None, stdout_file=None):
    """
    执行命令列表，可选重定向 stdin/out
    """
    try:
        stdin_handle = open(stdin_file, "r") if stdin_file else None
        stdout_handle = open(stdout_file, "w") if stdout_file else None

        subprocess.run(cmd_list, cwd=work_dir, check=True,
                       stdin=stdin_handle, stdout=stdout_handle, text=True)

        if stdin_handle:
            stdin_handle.close()
        if stdout_handle:
            stdout_handle.close()

        print(f"Command succeeded: {' '.join(cmd_list)}")
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd_list)}")
        print(e)

def automate_gaussian_amber(single_name, tleap_path, mol2_path):
    """
    自动化 Gaussian、Amber、acpype 流程，生成 GROMACS 拓扑文件
    """
    single_dir = os.path.join(TOP_DIR, single_name)
    generate_dir = os.path.join(single_dir, "GENERATE")
    os.makedirs(generate_dir, exist_ok=True)

    # 拷贝 mol2 和 tleap 文件到 GENERATE
    shutil.copy(mol2_path, os.path.join(generate_dir, f"{single_name}.mol2"))
    shutil.copy(tleap_path, os.path.join(generate_dir, os.path.basename(tleap_path)))

    # 设置工作目录
    work_dir = generate_dir

    # 1. 生成 Gaussian 输入文件
    gjf_file = f"{single_name}.gjf"
    run_command(["antechamber", "-i", f"{single_name}.mol2", "-fi", "mol2",
                 "-o", gjf_file, "-fo", "gcrt"], work_dir)

    # 2. 执行 Gaussian16
    run_command(["g16", gjf_file,  f"{single_name}.out"], work_dir)

    # 3. RESP 计算生成 prepin
    run_command(["antechamber", "-i", f"{single_name}.out", "-fi", "gout",
                 "-c", "resp", "-o", f"{single_name}.prepin", "-fo", "prepi"], work_dir)

    # 4. 使用 Amber 生成优化后的 mol2
    run_command(["antechamber", "-i", f"{single_name}.out", "-fi", "gout",
                 "-o", f"{single_name}.mol2", "-fo", "mol2", "-c", "resp", "-at", "amber"], work_dir)

    # 5. 检查缺失参数
    run_command(["parmchk2", "-i", f"{single_name}.mol2", "-f", "mol2",
                 "-o", f"{single_name}.frcmod"], work_dir)

    # 6. 执行 tleap
    run_command(["tleap", "-f", f"{single_name}_tleap.in"], work_dir)

    # 7. 使用 acpype 转化为 GROMACS
    run_command(["acpype", "-p", f"{single_name}.prmtop", "-x", f"{single_name}.inpcrd"], work_dir)

    # 8. 重命名拓扑文件，修改残基名
    acpype_output_dir = os.path.join(generate_dir, "MOL.amb2gmx")
    mol_gmx_top = os.path.join(acpype_output_dir, "MOL_GMX.top")
    final_top = os.path.join(TOP_DIR, f"{single_name}.top")


    if os.path.exists(mol_gmx_top):
        with open(mol_gmx_top, "r", encoding="utf-8") as f:
            content = f.read()
        # 替换残基名
        content = content.replace("MOL", residue_name)
        with open(final_top, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"已生成: {final_top}")
    else:
        print(f"Warning: {mol_gmx_top} not found!")


# def main():
#     settings = read_settings("settings.txt")

#     type_value = settings.get("type", "gromacs").lower()
#     if type_value == "gromacs":
#         single_param = settings.get("single")
#         if not single_param:
#             print("No 'single' parameter found in settings.")
#             return

#         # 支持单值或多值
#         single_list = [single_param] if isinstance(single_param, str) else single_param

#         for single_name in single_list:
#             result = generate_tleap_for_single(single_name)
#             if result:
#                 tleap_path, mol2_path = result
#                 automate_gaussian_amber(single_name, tleap_path, mol2_path)

#     elif type_value == "lammps":
#         # 预留 LAMMPS 处理逻辑
#         print("LAMMPS type detected. This part will be implemented later.")
#     else:
#         print(f"Unknown type '{type_value}' in settings. Skipping.")
    
#     #合并拓扑文件到MD_TEMP文件夹下 
#     itp_files = comb.process_top()
#     comb.generate_final_top(itp_files)

# if __name__ == "__main__":
#     main()