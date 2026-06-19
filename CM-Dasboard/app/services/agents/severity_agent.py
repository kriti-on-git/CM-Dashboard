from typing import Dict, Any
from .base_agent import BaseAgent
from app.services.ml.inference import MLInferenceService

class SeverityAgent(BaseAgent):
    """
    Agent responsible for predicting the severity of an incident based on its text,
    utilizing the ML Inference Service.
    """
    
    def __init__(self):
        self.inference = MLInferenceService()
    
    async def process(self, text: str, context: list = None, **kwargs) -> Dict[str, Any]:
        # Connect to the ML inference layer
        ml_result = self.inference.predict(text)
        
        # Use ML prediction to determine severity
        prediction = ml_result.get("prediction_class", "OTHER")
        severity = "LOW"
        confidence = ml_result.get("confidence", 0.50)
        
        if prediction in ["FIRE", "HAZMAT"]:
            severity = "CRITICAL"
        elif prediction in ["MEDICAL", "POLICE"]:
            severity = "HIGH"
            
        # RAG Context Injection
        if context:
            severity_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            reverse_scores = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
            
            context_score = 0.0
            total_weight = 0.0
            
            for case in context:
                sev = case.get("severity", "Unknown")
                if sev in severity_scores:
                    dist = case.get("distance", 1.0)
                    weight = 1.0 / (dist + 0.1)
                    context_score += severity_scores[sev] * weight
                    total_weight += weight
                    
            if total_weight > 0:
                avg_severity_score = round(context_score / total_weight)
                context_severity = reverse_scores.get(avg_severity_score, "LOW")
                
                # If context severity is higher than ML prediction, elevate the severity
                if avg_severity_score > severity_scores.get(severity, 1):
                    severity = context_severity
                    # Boost confidence because we matched a highly severe past incident
                    confidence = min(0.99, confidence + 0.20)
                elif context_severity == severity:
                    confidence = min(0.99, confidence + 0.10)
            
        return {
            "agent": "SeverityAgent",
            "severity": severity,
            "confidence": round(confidence, 2),
            "raw_ml_prediction": prediction
        }
