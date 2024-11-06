import os
import orjson as json
from automata.automata_config import AutomataConfig, AutomataConfigFactory
from config import Config
from automata.automata import Automata, AutomataDependencies, AutomataGraph
from docker_executor import DockerExecutor
from files_util import FileTree
from in_memory_graph_data import InMemoryGraphData
from sapient_langchain_openai import SapientLangchainOpanAI

evaluation = """
I need to make a website that uses a flexible layout that works on
both mobile and desktop. This is a brochure website for a client that 
sells toast at a toast restaurant. We will need a "Home", "About", "Menu",
"Contact Us", and "Locations" sections, with expected sub-pages. 

This should use a modern UI framework like React, along with nice looking UI
components; something like Material UI but maybe less derivative. Please make 
up content for the website, including a "History of toast" page, and some other
fun stuff.

Respond in pure JSON, no Markdown formatting please.

"""
if __name__ == "__main__":
    config = Config.get_instance()
    sapient = SapientLangchainOpanAI(config)
    automata_config_dict = config.load_config_file(
            config.normalize_and_resolve_path(config.conf.automata_location))
    
    automata_global_config = automata_config_dict['config']
    automata_dag_list: list[dict] = automata_config_dict["automata"]
    in_memory_graph_data: InMemoryGraphData = InMemoryGraphData()
    automata_configs: list[AutomataConfig] = []
    for dag_node in automata_dag_list:
        automata_config = AutomataConfigFactory(dag_node).get_config()
        automata_configs.append(automata_config)
        
    # Import handlers to register them:
    from js_handler import JSHandler
    from py_handler import PyHandler
    from native_handler import NativeHandler
    NativeHandler.set_graph_data(in_memory_graph_data)
 
    dependencies: AutomataDependencies = AutomataDependencies(
        config, automata_configs, sapient, 
        in_memory_graph_data, automata_global_config=automata_global_config)
    graph: AutomataGraph = AutomataGraph(dependencies)
    
    automatons: list[Automata] = graph.run_graph(initial_input=evaluation)
    config.logger.info("Automaton results: ")
    for automata in automatons:
        config.logger.info(json.dumps(automata.step_data, option=json.OPT_INDENT_2).decode("utf-8"))
