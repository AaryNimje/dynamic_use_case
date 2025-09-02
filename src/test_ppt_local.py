import json
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from orchestrator import AgenticWAFROrchestrator

def test_ppt_generation():
    """Test PPT generation locally."""
    
    # Create orchestrator
    orchestrator = AgenticWAFROrchestrator()
    
    # Test payload for PPT generation
    test_payload = {
        "action": "start",
        "company_name": "TechCorp Solutions",
        "company_url": "https://www.techcorp.com",
        "output_format": "ppt",  # Generate PPT only
        "presentation_style": "executive",
        "session_id": f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "project_id": "test-project",
        "user_id": "test-user",
        "prompt": "Create a comprehensive business transformation presentation focusing on AI-powered automation solutions for manufacturing operations. Include use cases for predictive maintenance, quality control, and supply chain optimization with realistic ROI projections.",
        "files": [],  # No files for initial test
        "custom_requirements": "Focus on conservative ROI estimates and implementation timelines"
    }
    
    print("🚀 Starting PPT generation test...")
    print(f"Company: {test_payload['company_name']}")
    print(f"Output Format: {test_payload['output_format']}")
    print(f"Style: {test_payload['presentation_style']}")
    print("=" * 50)
    
    try:
        # Process request
        result = orchestrator.process_request(test_payload)
        
        # Display results
        print(f"\n✅ Status: {result.get('status')}")
        print(f"📊 Use Cases Generated: {result.get('total_use_cases', 0)}")
        
        if result.get('presentation_url'):
            print(f"📎 PowerPoint URL: {result['presentation_url']}")
        
        if result.get('report_url'):
            print(f"📄 PDF Report URL: {result['report_url']}")
            
        print(f"🔍 Session ID: {result.get('session_id')}")
        
        # Show use cases
        if result.get('use_cases'):
            print(f"\n📋 Generated Use Cases:")
            for i, uc in enumerate(result['use_cases'][:3], 1):
                print(f"{i}. {uc.get('title', 'Unknown Title')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_ppt_generation()