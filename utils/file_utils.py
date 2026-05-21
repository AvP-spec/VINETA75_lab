import pandas as pd
from datetime import datetime
from pathlib import Path, PurePath
import os
import sys
import getpass
import json
from PyQt6.QtWidgets import QApplication, QFileDialog
# from PyQt6 import QtWidgets
# from typing import Union

RELATIVE_BASE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
ABS_DIR_PATH = Path.home() / RELATIVE_BASE_PATH

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.terminal_styler import TerminalColours

tc = TerminalColours()


def make_data_dir(
        base_path: str = RELATIVE_BASE_PATH, 
        base_name: str = "",
        )-> Path:
    """
    Creates directory and returns its path for today's experiment.
    Format: base_dir / YYYY-MM-DD_user_base_name
    If base_path is absolute, uses it as is.
    If base_path is relative, joins it with Path.home().
    """
    provided_path = Path(base_path)
    if provided_path.is_absolute():
        base_dir = provided_path
    else:
        # get path to user folder
        base_dir = Path.home() / provided_path

    now = datetime.now()
    user = getpass.getuser()
    date_str = f"{now.strftime('%Y-%m-%d')}_{user}"

    if not base_name:
        target_dir = base_dir / date_str
    elif base_name.startswith(("/", "\\")):
        clean_name = base_name.lstrip("/\\") # to not be confused with root
        sub_path = PurePath(clean_name) # if more subfolders
        target_dir = base_dir / date_str / sub_path
    else:
        target_dir = base_dir / f"{date_str}_{base_name}"

    target_dir.mkdir(parents=True, exist_ok=True)

    return target_dir


def make_data_file_name(
        data_dir: str | Path, # Union[str, Path], 
        base_name:str="",
        extension: str = "csv"
        ) -> Path:
    
    """
    Generates a full path for a data file with a timestamp.
    Format: data_dir / hh-mm-ss_base_name.extension
    """
    data_dir = Path(data_dir)
    now = datetime.now()
    time_str = now.strftime("%H-%M-%S") # hh-mm-ss
    name_part = f"_{base_name}" if base_name else ""
    file_name = f"{time_str}{name_part}.{extension}"
    
    return data_dir / file_name


def save_dataframe(
        df: pd.DataFrame, 
        file_path: Path, 
        metadata: dict = None,
        sep: str = '\t', # ","
        index: bool = True,
        silent: bool = False,
        **kwards # kwards for pd.DataFrame.to_csv
        ):
    
    if not silent:
        print( "save_dataframe from from utils.terminal_styler")

    human_lines = []
    human_lines.append(f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if metadata:
        for key, value in metadata.items():
            human_lines.append(f"# {key}: {value}")
        
        # all header in one JSON line 
        meta_json = json.dumps(metadata, ensure_ascii=False)
        human_lines.append(f"# JSON_META: {meta_json}")

        num_header_lines = len(human_lines) + 2

        header = (f"# Header-Lines: {num_header_lines}\n" 
                  + "\n".join(human_lines) + "\n")
        # extra empty line to separate the header
        header += "\n"
    else:
        header = ''

    tc = TerminalColours()
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(header)
            df.to_csv(f, sep=sep, index=index, **kwards)
        if not silent:
            print(f"{tc.GREEN} data frame saved to: {tc.RESET}")
            print(f"{file_path} \n")
        return True
    except Exception as e:
        print(f"{tc.RED} Error save_dataframe from utils.terminal_styler")
        print(f"Error: {e}")
        return False


def select_file(default_dir=ABS_DIR_PATH, filter="All Files (*)"):
    app = QApplication.instance() or QApplication(sys.argv)
    file_path, _ = QFileDialog.getOpenFileName(
        parent      = None,                             # do not connect the new window to pevious App
        caption     = 'file_utils: Select file',        # window title
        directory   = str(default_dir),
        filter      = filter
    )
    app.processEvents()  
    return file_path if file_path else None


def select_folder(default_dir=ABS_DIR_PATH):
    app = QApplication.instance() or QApplication(sys.argv)
    folder_path = QFileDialog.getExistingDirectory(
        parent      = None,
        caption     = 'file_utils: Select folder',
        directory   = str(default_dir),
        #options=QFileDialog.Option.ShowDirsOnly  # Shows only folders
    )
    app.processEvents()

    return folder_path if folder_path else None


def read_file_header(filepath):
    header = {}
    header_lines = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline()

        if not first_line.startswith('# Header-Lines:'):
            print(f"file_utils.read_file_header {tc.MAGENTA} Warning:")
            print(f"# Header-Lines:{tc.RESET} not found in {filepath}")
            print(f"{tc.MAGENTA}# Header-Lines{tc.RESET} set to 0")
            return header, header_lines
        
        header_lines = int(first_line.split(':')[-1].strip())
        header_content = [first_line] + [f.readline() for _ in range(header_lines - 1)]

        if header_content[-2].startswith("# JSON_META:"):
            json_data = header_content[-2].split('# JSON_META:', 1)[1].strip()
            header = json.loads(json_data)

        else:
            print(f"file_utils.read_file_header {tc.MAGENTA} Warning:")
            print(f"# JSON_META:{tc.RESET} not found in {filepath}")

        return (header, header_lines)
 
    
def read_file(filepath, header_lines:int=None, separator="\t" ):
    header = {}
    if header_lines == None:
        header, n_lines = read_file_header(filepath=filepath)
    else:
        n_lines = header_lines

    df = pd.read_csv(
        filepath,
        skiprows=n_lines,
        sep=separator,
        comment='#' # skipping lines started with this sign
    )

    return df, header
    


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')

    rpath = RELATIVE_BASE_PATH / "test_output_delete_me"


    def test_make_data_dir(rpath=rpath):
        test_cases = [
        "",                             # Empty (default folder)
        "experiment_v1",                # Simple string (suffix)
        "/sub_folder",                  # Leading forward slash (subfolder)
        "\\sub_folder_win",             # Leading backslash (subfolder)
        "/sub1/sub2",                   # Multiple levels (Linux style)
        "\\sub1\\sub2",                 # Multiple levels (Windows style)
        "///double_slashes",            # Messy leading slashes
        "hint_name/subfolder"
    ]
        
        print(f"{'INPUT (base_name)':<25} | {'RESULTING PATH'}")
        print("-" * 80)
        
        
        for case in test_cases:
            try:
                result_path = make_data_dir(base_path=rpath, base_name=case)
                print(f"{repr(case):<25} | {result_path}")
            except Exception as e:
                print(f"{repr(case):<25} | Error: {e}")

        print("-" * 80)

   # test_make_data_dir()


    def test_save_dataframe():
        test_df = pd.DataFrame({
        'time_s': [0.0, 0.6, 1.2, 1.8, 2.4],
        'piezo_V': [-10.0, -5.0, 0.0, 5.0, 10.0],
        'wavelength_nm': [780.241, 780.243, 780.245, 780.247, 780.249]
        })

        test_meta = {
        "project": "Unit_Test_Project",
        "operator": getpass.getuser(),
        "v_step": 5.0,
        "n_wlm": 1,
        "notes": "Testing file_utils architecture"
        }

        data_dir = make_data_dir(
                    base_path=rpath,
                    base_name="save_test"
                    )
        f_name = make_data_file_name(data_dir=data_dir, base_name="AI_df")
        success = save_dataframe(
                                 test_df, 
                                 file_path=f_name, 
                                 metadata=test_meta,
                                 sep='\t',
                                 index=True,
                                 silent=False,
                                 )

        return success

    test_save_dataframe()


    file_path = select_file()
    print(file_path)
    # header, n_lines = read_file_header(filepath=file_path)
    # print(header)

    df, header = read_file(filepath=file_path)
    print(df.head())
    print(header)

    # folder_path = select_folder()
    # print(folder_path)











