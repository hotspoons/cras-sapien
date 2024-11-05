
import os

from config import Config
from graph_data import StepData
from native_handler import NativeHandler

class FileTree:
    app_config = Config.get_instance()  
    
    def file_tree_output_handler(input_step_datas: list[StepData], 
                             all_step_datas: list[StepData], step_data: StepData, 
                             config: dict, input: str):
        
        NativeHandler.CALLBACKS[NativeHandler.DEFAULT_OUTPUT_HANDLER](
            input_step_datas=input_step_datas, 
            all_step_datas=all_step_datas,
            step_data=step_data, 
            config=config, 
            input=input)
        if isinstance(step_data.output_data, dict) :
            FileTree.write_tree(step_data.output_data,  os.path.abspath(FileTree.app_config.conf.working_folder) + '/' + step_data.session_id)
    
    NativeHandler.register_callback('file_tree_output_handler', file_tree_output_handler)
        
    def write_tree(tree: dict[str, str|dict], base_path: str):
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        for name, contents_or_subfolder in tree.items():
            if '../' in name:
                raise Exception('Path traversal detected, aborting')
            if isinstance(contents_or_subfolder, str):
                with open(base_path + '/' + name, "w") as f:
                    f.write(contents_or_subfolder)
                    # TODO permissions
            elif isinstance(contents_or_subfolder, dict):
                path = base_path + '/' + name if name != '.' else base_path
                FileTree.write_tree(contents_or_subfolder, path)
            else:
                print("Unknown type found in file tree: {}".format(contents_or_subfolder))
                
                    