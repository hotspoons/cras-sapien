from langchain_openai import ChatOpenAI

from config import Config
from sapient import Sapient

class SapientLangchainOpanAI(Sapient):
    def __init__(self, config: Config):
        self.config = config
        self.conf = config.get_conf()
        self.logger = config.logger

    # TODO tool calling, for now depend on prompts
    def invoke_llm(self, system_message: str, step_input: str, model: str = None) -> str:
        model = model if model != None else self.conf.model_name
        llm_config = {
            "model": model
        }
        if self.conf.base_url != "":
            llm_config["base_url"] = self.conf.base_url
        if self.conf.api_key != "":
            llm_config["api_key"] = self.conf.api_key
        
        llm_config = self.config.merge_override_params_key("llm_config", llm_config)
        llm = ChatOpenAI(**llm_config)
        response = llm.invoke([
            ("system", system_message),
            ("human", step_input),
        ])
        content = str(response.content)
        return content