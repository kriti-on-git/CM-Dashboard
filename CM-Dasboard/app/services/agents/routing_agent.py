from typing import Dict, Any
from .base_agent import BaseAgent

class RoutingAgent(BaseAgent):
    """
    Agent responsible for assigning incidents to the proper team or specific agent.
    Takes the output of other agents (severity, type) as context.
    """
    
    async def process(self, text: str, severity: str = None, incident_type: str = None, context: list = None, **kwargs) -> Dict[str, Any]:
        """
        Routes the incident. Optionally utilizes pre-computed severity, incident_type, and RAG context.
        """
        assigned_team = "GENERAL_SUPPORT"
        
        # Determine team based on type
        if incident_type == "FIRE":
            assigned_team = "FIRE_DEPARTMENT"
        elif incident_type == "MEDICAL":
            assigned_team = "EMS"
        elif incident_type == "POLICE":
            assigned_team = "LAW_ENFORCEMENT"
        elif incident_type == "HAZMAT":
            assigned_team = "HAZMAT_RESPONSE"
            
        # RAG Context Injection for team routing
        # If the incident type is unknown, but past similar cases were routed to a specific team, use that.
        if context and assigned_team == "GENERAL_SUPPORT":
            for case in context:
                cat = case.get("category", "Unknown")
                if cat == "FIRE":
                    assigned_team = "FIRE_DEPARTMENT"
                    break
                elif cat == "MEDICAL":
                    assigned_team = "EMS"
                    break
                elif cat == "POLICE":
                    assigned_team = "LAW_ENFORCEMENT"
                    break
                elif cat == "HAZMAT":
                    assigned_team = "HAZMAT_RESPONSE"
                    break
            
        # Determine priority based on severity
        priority = "NORMAL"
        if severity in ["HIGH", "CRITICAL"]:
            priority = "EXPEDITED"
            
        return {
            "agent": "RoutingAgent",
            "assigned_team": assigned_team,
            "priority": priority,
            "requires_human_review": severity == "CRITICAL"
        }
