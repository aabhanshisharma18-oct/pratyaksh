from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass
class AnalysisResult:
    format_support:str;decoding:str;analysis:str;algorithm:str;version:str;parameters:dict
    findings:dict;artifacts:list;interpretation:str;limitations:list;evaluation:dict|None=None
    def dict(self): return asdict(self)

class Analyzer:
    name="";version="1.0"
    def analyze(self,*args,**kwargs)->AnalysisResult: raise NotImplementedError
