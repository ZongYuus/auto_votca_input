from read_settings import read_settings
import combine_top as comb
from generate_top import generate_tleap_for_single 
from generate_top import automate_gaussian_amber
from auto_md import prepare_workdir
from auto_md import build_supercell
from auto_md import run_mdp_pipeline
from auto_mapping import auto_mapping


def main():
    settings = read_settings("settings.txt")

    type_value = settings.get("type", "gromacs").lower()
    if type_value == "gromacs":
        single_param = settings.get("single")
        if not single_param:
            print("No 'single' parameter found in settings.")
            return

        # 支持单值或多值
        single_list = [single_param] if isinstance(single_param, str) else single_param

        for single_name in single_list:
            result = generate_tleap_for_single(single_name)
            if result:
                tleap_path, mol2_path = result
                automate_gaussian_amber(single_name, tleap_path, mol2_path)

        #合并拓扑文件到MD_TEMP文件夹下 
        itp_files = comb.process_top()
        comb.generate_final_top(itp_files)

        """
        主流程：
        1. 读取 settings
        2. 准备工作目录
        3. 构建 supercell
        """
        settings = read_settings("settings.txt")

        # Step 1: 准备 MD_TEMP 并复制输入文件
        workdir = prepare_workdir(settings)

        # Step 2: 执行 gmx genconf
        build_supercell(settings, workdir)

        # Step 3: 跑md
        run_mdp_pipeline(settings)

        # Step 4: 生成mapping 和 hdf5

        auto_mapping(settings)

#---------------------------------------分割线------------------------------------------------------#

    elif type_value == "lammps":
        # 预留 LAMMPS 处理逻辑
        print("LAMMPS type detected. This part will be implemented later.")
    else:
        print(f"Unknown type '{type_value}' in settings. Skipping.")

if __name__ == "__main__":
    main()
 