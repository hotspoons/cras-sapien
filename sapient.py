from abc import abstractmethod

class Sapient:
    
    @abstractmethod
    def invoke_llm(system_message: str, step_input: str) -> str:
        pass