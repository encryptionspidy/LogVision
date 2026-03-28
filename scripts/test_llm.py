import sys
import os

# Add project root to python path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm.router import LLMRouter

def test_llm():
    print("Testing LLM generation...")
    router = LLMRouter()
    
    # Test primary LLM routing
    prompt = "Reply with 'Hello, this is a test' and verify it's a string response."
    try:
        res = router._route(prompt)
        print(f"Status: {res['status']}")
        print(f"Response: {res['text']}")
        assert isinstance(res['text'], str)
        print("SUCCESS\n")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_llm()
