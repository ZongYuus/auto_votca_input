import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from generate_top import get_residue_name_from_pdb


def get_last_md_name(settings):
    if "mdp" not in settings or settings["mdp"] == "default":
        return "nvt"

    mdp_list = settings["mdp"]
    if isinstance(mdp_list, str):
        mdp_list = [mdp_list]

    return os.path.splitext(mdp_list[-1])[0]


def collect_mapping_outputs(mapping_root):
    qc_root = os.path.join(mapping_root, "QC_FILES")
    mp_root = os.path.join(mapping_root, "MP_FILES")

    os.makedirs(qc_root, exist_ok=True)
    os.makedirs(mp_root, exist_ok=True)

    subdirs = [
        d for d in os.listdir(mapping_root)
        if os.path.isdir(os.path.join(mapping_root, d))
    ]

    frag_counter = 1

    for sub in subdirs:
        subdir = os.path.join(mapping_root, sub)

        # QC_FILES
        qc_src = os.path.join(subdir, "QC_FILES")
        if os.path.exists(qc_src):
            for f in os.listdir(qc_src):
                shutil.copy(os.path.join(qc_src, f), qc_root)

        # MP_FILES
        mp_src = os.path.join(subdir, "MP_FILES")
        if os.path.exists(mp_src):
            for f in os.listdir(mp_src):
                shutil.copy(os.path.join(mp_src, f), mp_root)

        # fragment + XML
        xml_path = os.path.join(subdir, "mapping.xml")
        if not os.path.exists(xml_path):
            continue

        tree = ET.parse(xml_path)
        root = tree.getroot()

        fragments = root.findall(".//fragment")

        for frag in fragments:
            name_node = frag.find("name")
            if name_node is None:
                continue

            old_name = name_node.text
            new_name = f"fragment{frag_counter}"

            old_pdb = os.path.join(subdir, f"{old_name}.pdb")
            new_pdb = os.path.join(mapping_root, f"{new_name}.pdb")

            if os.path.exists(old_pdb):
                shutil.copy(old_pdb, new_pdb)

            name_node.text = new_name
            frag_counter += 1

        tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def auto_mapping(settings):
    mapping_root = "MAPPING"
    md_temp_dir = "MD_TEMP"
    source_dir = "MOL_FILES"

    os.makedirs(mapping_root, exist_ok=True)

    # ===== settings =====
    if "single" not in settings:
        raise ValueError("Missing 'single' in settings")

    single_list = settings["single"]
    if isinstance(single_list, str):
        single_list = [single_list]

    if "orca" not in settings:
        raise ValueError("Missing 'orca' in settings")

    orca_path = settings["orca"]

    cores = int(settings.get("cores", 1))

    # ===== Step 1 =====
    for pdb_name in single_list:

        pdb_file = pdb_name + ".pdb"
        src_pdb = os.path.join(source_dir, pdb_file)

        if not os.path.exists(src_pdb):
            raise FileNotFoundError(f"{src_pdb} not found")

        workdir = os.path.join(mapping_root, pdb_name)
        os.makedirs(workdir, exist_ok=True)

        shutil.copy(src_pdb, os.path.join(workdir, pdb_file))

        resname = get_residue_name_from_pdb(src_pdb)

        cmd1 = [
            "xtp_autogen_mapping",
            "-pdb", pdb_file,
            "-s", "n", "e", "h",
            "-orca", orca_path,
            "-f", "b3lyp",
            "-b", "6-31g",
            "-m", resname,
            "-opt"
        ]

        subprocess.run(cmd1, cwd=workdir, check=True)

    # ===== Step 2 =====
    collect_mapping_outputs(mapping_root)

    # ===== Step 3: merge xml =====
    molecules = []

    subdirs = [
        d for d in os.listdir(mapping_root)
        if os.path.isdir(os.path.join(mapping_root, d))
    ]

    for sub in subdirs:
        xml_path = os.path.join(mapping_root, sub, "mapping.xml")

        if not os.path.exists(xml_path):
            continue

        tree = ET.parse(xml_path)
        root = tree.getroot()

        mol = root.find("./molecules/molecule")
        if mol is not None:
            molecules.append(mol)

    new_root = ET.Element("topology")
    mols_node = ET.SubElement(new_root, "molecules")

    for mol in molecules:
        mols_node.append(mol)

    merged_xml = os.path.join(mapping_root, "mapping.xml")
    ET.ElementTree(new_root).write(
        merged_xml, encoding="utf-8", xml_declaration=True
    )

    # ===== Step 4: MD files =====
    md_files_dir = os.path.join(mapping_root, "MD_FILES")
    os.makedirs(md_files_dir, exist_ok=True)

    last_name = get_last_md_name(settings)

    gro_file = f"{last_name}.gro"
    tpr_file = f"{last_name}.tpr"

    for f in [gro_file, tpr_file]:
        src = os.path.join(md_temp_dir, f)
        dst = os.path.join(md_files_dir, f)

        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} not found")

        shutil.copy(src, dst)

    # ===== Step 5: xtp_map =====
    cmd2 = [
        "xtp_map",
        "-v",
        "-t", f"MD_FILES/{tpr_file}",
        "-c", f"MD_FILES/{gro_file}",
        "-s", "mapping.xml",
        "-f", "state.hdf5"
    ]

    subprocess.run(cmd2, cwd=mapping_root, check=True)

    # ===== Step 6: xtp_run =====
    subprocess.run(
        ["xtp_run", "-e", "mapchecker", "-c", "map_file=mapping.xml", "-f", "state.hdf5"],
        cwd=mapping_root, check=True
    )

    subprocess.run(
        [
            "xtp_run", "-e", "neighborlist",
            "-c", "exciton_cutoff=0.5", "constant=0.6",
            "-f", "state.hdf5",
            "-t", str(cores)
        ],
        cwd=mapping_root, check=True
    )

    subprocess.run(
        [
            "xtp_run", "-e", "einternal",
            "-c", "energies_file=mapping.xml",
            "-f", "state.hdf5"
        ],
        cwd=mapping_root, check=True
    )

# # ======= 使用示例 =======
# from read_settings import read_settings

# if __name__ == "__main__":
#     settings = read_settings("settings.txt")
#     auto_mapping(settings)
