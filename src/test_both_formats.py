import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from orchestrator import AgenticWAFROrchestrator

def test_both_formats():
    """Test both PDF and PPT generation."""
    
    orchestrator = AgenticWAFROrchestrator()
    
    test_payload = {
        "action": "start",
        "company_name": "InnovateTech Inc",
        "output_format": "both",  # Generate both PDF and PPT
        "presentation_style": "technical",
        "session_id": f"both-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "prompt": "Create presentations for our cloud migration strategy including data modernization, security enhancements, and cost optimization use cases."
    }
    
    print("🚀 Testing both PDF and PPT generation...")
    
    try:
        result = orchestrator.process_request(test_payload)
        
        print(f"\n✅ Status: {result.get('status')}")
        print(f"📊 Use Cases: {result.get('total_use_cases', 0)}")
        
        # Check both outputs
        output_urls = result.get('output_urls', {})
        if output_urls.get('pdf_report'):
            print(f"📄 PDF Report: {output_urls['pdf_report']}")
        if output_urls.get('ppt_presentation'):
            print(f"📎 PowerPoint: {output_urls['ppt_presentation']}")
            
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_both_formats()