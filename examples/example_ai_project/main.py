"""Example AI project with intentional issues for testing Merit Analyzer."""

import os
import json
from typing import Dict, Any, Optional
import time


class PricingAgent:
    """AI agent for handling pricing inquiries."""
    
    def __init__(self):
        self.pricing_data = {
            "basic": {"price": 9, "features": ["Basic features"]},
            "pro": {"price": 49, "features": ["Pro features", "Priority support"]},
            "enterprise": {"price": 199, "features": ["All features", "24/7 support", "Custom integration"]}
        }
        self.timeout_seconds = 5  # Too short for complex requests
    
    def handle_pricing_inquiry(self, user_input: str) -> str:
        """Handle pricing-related inquiries."""
        # Issue 1: No input validation
        if not user_input:
            return "Internal server error"  # Should return proper error message
        
        # Issue 2: Vague responses for specific questions
        if "pro plan" in user_input.lower():
            return "We have various pricing tiers available"  # Should return specific price
        
        if "enterprise" in user_input.lower():
            return "Please contact sales for enterprise pricing"  # Should return direct price
        
        if "all plans" in user_input.lower():
            return "Our plans start at $9/month"  # Should return complete pricing
        
        # Issue 3: No timeout handling for complex requests
        if "complex" in user_input.lower() and "report" in user_input.lower():
            time.sleep(35)  # Simulate long-running operation
            return "Report generated successfully"
        
        return "I can help you with pricing information. What would you like to know?"
    
    def get_pricing_info(self, plan: str) -> Optional[Dict[str, Any]]:
        """Get pricing information for a specific plan."""
        return self.pricing_data.get(plan.lower())


class SupportAgent:
    """AI agent for handling support inquiries."""
    
    def __init__(self):
        self.knowledge_base = {
            "password reset": "Go to Settings > Security > Reset Password",
            "billing": "Contact billing@company.com",
            "technical": "Submit a ticket in the support portal"
        }
    
    def handle_support_inquiry(self, user_input: str) -> str:
        """Handle support-related inquiries."""
        # This agent works correctly
        user_input_lower = user_input.lower()
        
        for topic, response in self.knowledge_base.items():
            if topic in user_input_lower:
                return response
        
        return "I can help you with common support topics. What do you need help with?"


class AIAssistant:
    """Main AI assistant that routes requests to specialized agents."""
    
    def __init__(self):
        self.pricing_agent = PricingAgent()
        self.support_agent = SupportAgent()
    
    def process_request(self, user_input: str) -> Dict[str, Any]:
        """Process a user request and return response."""
        start_time = time.time()
        
        try:
            # Route to appropriate agent
            if any(word in user_input.lower() for word in ["price", "cost", "plan", "pricing"]):
                response = self.pricing_agent.handle_pricing_inquiry(user_input)
                category = "pricing"
            elif any(word in user_input.lower() for word in ["help", "support", "password", "billing"]):
                response = self.support_agent.handle_support_inquiry(user_input)
                category = "support"
            else:
                response = "I can help you with pricing or support questions. What do you need?"
                category = "general"
            
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "response": response,
                "category": category,
                "execution_time_ms": int(execution_time),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "category": "error",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "status": "error"
            }


def main():
    """Main function for testing the AI assistant."""
    assistant = AIAssistant()
    
    # Test cases
    test_cases = [
        "How much does the pro plan cost?",
        "What's the cost of the enterprise plan?",
        "How do I reset my password?",
        "Show me pricing for all plans",
        "Generate a complex report with 1000 data points",
        ""  # Empty input test
    ]
    
    print("🤖 AI Assistant Test Results:")
    print("=" * 50)
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_input or '(empty input)'}")
        result = assistant.process_request(test_input)
        print(f"Response: {result['response']}")
        print(f"Category: {result['category']}")
        print(f"Execution time: {result['execution_time_ms']}ms")
        print(f"Status: {result['status']}")


if __name__ == "__main__":
    main()
