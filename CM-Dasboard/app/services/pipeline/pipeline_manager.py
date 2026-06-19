from typing import Dict, Any
import uuid
from app.services.agents.intelligent_agent import IntelligentAgent
from app.services.memory.faiss_memory import FaissMemory
from app.services.memory.retriever import ContextRetriever

class PipelineManager:
    """
    Orchestrates the execution of the AI agent to process an incident.
    Now utilizes a unified IntelligentAgent powered by RAG context.
    """
    
    def __init__(self):
        self.intelligent_agent = IntelligentAgent()
        self.memory = FaissMemory()
        self.retriever = ContextRetriever()

    async def process_incident(self, text: str) -> Dict[str, Any]:
        """
        Runs the incident text through the intelligent agent pipeline.
        
        Args:
            text (str): The raw text description of the incident.
            
        Returns:
            Dict[str, Any]: The enriched, combined output.
        """
        combined_result = {"original_text": text}
        incident_id = str(uuid.uuid4())
        
        # 0. Retrieve similar past incidents from FAISS memory via Context Retriever
        retriever_result = self.retriever.get_context(text, top_k=3)
        similar_incidents = retriever_result.get("similar_cases", [])
        combined_result["similar_incidents_context"] = similar_incidents
        
        # 1. Process via Unified Intelligent Agent
        agent_result = await self.intelligent_agent.process(text, context=similar_incidents)
        combined_result["intelligent_analysis"] = agent_result
        
        incident_type = agent_result.get("category", "OTHER")
        severity = agent_result.get("severity", "LOW")
        assigned_team = agent_result.get("department", "GENERAL_SUPPORT")
        
        # 2. Generate final top-level summary combining all decisions
        final_decision = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "severity_level": severity,
            "assigned_team": assigned_team,
            "priority": "EXPEDITED" if severity in ["HIGH", "CRITICAL"] else "NORMAL",
            "requires_human_review": severity == "CRITICAL",
            "reasoning": agent_result.get("reason", "")
        }
        combined_result["final_decision"] = final_decision
        
        # 3. Store the final enriched incident result into FAISS memory
        self.memory.add_memory(text=text, metadata=final_decision)
        
        return combined_result
