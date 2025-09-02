import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from orchestrator import AgenticWAFROrchestrator

def test_all_styles():
    """Test all presentation styles."""
    
    styles = ['executive', 'technical', 'marketing', 'strategy']
    orchestrator = AgenticWAFROrchestrator()
    
    for style in styles:
        print(f"\n🎨 Testing {style.upper()} style...")
        
        test_payload = {
            "action": "start",
            "company_name": f"TestCorp {style.title()}",
            "output_format": "ppt",
            "presentation_style": style,
            "session_id": f"{style}-test-{datetime.now().strftime('%H%M%S')}",
            "prompt": f"Create a {style} presentation for digital transformation initiatives."
        }
        
        try:
            result = orchestrator.process_request(test_payload)
            print(f"✅ {style.title()} style: {result.get('status')}")
            if result.get('presentation_url'):
                print(f"📎 URL: {result['presentation_url']}")
        except Exception as e:
            print(f"❌ {style.title()} failed: {e}")

if __name__ == "__main__":
    test_all_styles()