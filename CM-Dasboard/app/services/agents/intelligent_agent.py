from typing import Dict, Any, List
import json
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class IntelligentAgent(BaseAgent):
    """
    Unified Intelligent Crisis Management AI Agent.
    Utilizes a master system prompt to evaluate Classification, Severity, and Routing
    simultaneously based on the incident text and RAG context.
    """
    
    SYSTEM_PROMPT = """You are an intelligent Crisis Management AI Agent inside CM-Dashboard.

Your job is to analyze incidents using:
1. Current input data (user incident)
2. Retrieved historical incidents from FAISS (RAG context)
3. Learned patterns from past decisions

------------------------
INPUT:
- Incident text: {incident}
- Retrieved context: {context}

------------------------
GOALS:

1. CLASSIFICATION:
- Predict the correct incident category
- Use BOTH:
  - semantic understanding
  - historical matches

2. SEVERITY:
- Predict severity (LOW, MEDIUM, HIGH, CRITICAL)
- If similar past incidents had HIGH severity -> bias towards HIGH

3. ROUTING:
- Assign correct department
- If 2+ past incidents agree -> follow historical routing

------------------------
REASONING RULES:

- If similarity score > 0.8 -> strongly trust memory
- If 2+ past cases match -> override weak predictions
- If no strong match -> rely on model prediction

------------------------
OUTPUT FORMAT:

{{
  "category": "...",
  "severity": "...",
  "department": "...",
  "confidence": 0.95,
  "reason": "Explain decision using both input + past incidents"
}}

------------------------
IMPORTANT:

- Always explain whether decision came from:
  - current input OR
  - historical memory OR
  - both

- Prefer consistency with past decisions (learning behavior)

You are NOT a rule-based system.
You are a learning system with memory.
"""

    async def process(self, text: str, context: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Formats the prompt with the incident text and context, and ideally queries an LLM.
        """
        # Format the RAG context cleanly for the prompt
        formatted_context = "No historical context found."
        if context:
            formatted_context = json.dumps(context, indent=2)
            
        # 1. Compile the prompt
        prompt = self.SYSTEM_PROMPT.format(
            incident=text,
            context=formatted_context
        )
        
        logger.info(f"Compiled LLM Prompt (Length: {len(prompt)} chars)")
        
        # 2. Query the LLM
        # TODO: Integrate with Langchain / OpenAI / Local LLM here using the `prompt`.
        # For now, we return a structured mock response reflecting the new unified output format.
        
        # Mocking an intelligent response based on simplistic keyword parsing just so the pipeline runs
        text_lower = text.lower()
        category = "OTHER"
        severity = "LOW"
        department = "GENERAL_SUPPORT"
        
        if any(word in text_lower for word in ["fire", "burn"]):
            category = "FIRE"
            severity = "CRITICAL"
            department = "FIRE_DEPARTMENT"
        elif any(word in text_lower for word in ["medical", "injured"]):
            category = "MEDICAL"
            severity = "HIGH"
            department = "EMS"
            
        if context:
            # Fake the LLM leveraging memory
            reason = "Decision derived from both input text and historical memory matches."
        else:
            reason = "Decision derived purely from semantic understanding of input."
            
        llm_response_json = {
            "category": category,
            "severity": severity,
            "department": department,
            "confidence": 0.85,
            "reason": reason
        }
        
        return llm_response_json
