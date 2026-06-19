from typing import Dict, Any
from .base_agent import BaseAgent

class ClassificationAgent(BaseAgent):
    """
    Agent responsible for predicting the specific type or category of an incident.
    """
    
    async def process(self, text: str, context: list = None, **kwargs) -> Dict[str, Any]:
        text_lower = text.lower()
        incident_type = "OTHER"
        confidence = 0.50
        
        # Base heuristic logic
        if any(word in text_lower for word in ["fire", "smoke", "burn", "arson"]):
            incident_type = "FIRE"
            confidence = 0.80
        elif any(word in text_lower for word in ["medical", "injured", "blood", "heart attack", "unconscious"]):
            incident_type = "MEDICAL"
            confidence = 0.80
        elif any(word in text_lower for word in ["gun", "robbery", "police", "assault", "trespassing"]):
            incident_type = "POLICE"
            confidence = 0.80
        elif any(word in text_lower for word in ["leak", "chemical", "hazard", "spill"]):
            incident_type = "HAZMAT"
            confidence = 0.80
            
        # RAG Context Injection & Weighted Voting
        if context:
            category_counts = {}
            for case in context:
                cat = case.get("category", "Unknown")
                if cat != "Unknown":
                    # Weight by inverse distance (closer = higher weight)
                    dist = case.get("distance", 1.0)
                    weight = 1.0 / (dist + 0.1)
                    category_counts[cat] = category_counts.get(cat, 0) + weight
                    
            if category_counts:
                # Find the most common category in similar past incidents
                top_context_category = max(category_counts, key=category_counts.get)
                
                # If context agrees with heuristic, boost confidence
                if top_context_category == incident_type:
                    confidence = min(0.99, confidence + 0.15)
                # If heuristic is weak ("OTHER") but context is strong, override it
                elif incident_type == "OTHER":
                    incident_type = top_context_category
                    confidence = 0.70
                    
        return {
            "agent": "ClassificationAgent",
            "type": incident_type,
            "confidence": round(confidence, 2)
        }
