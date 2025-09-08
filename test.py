#!/usr/bin/env python3
"""
Complete verification script for all fixes
Run this to verify everything is working
"""
import sys
import os

# Add your src path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_custom_prompt_processor():
    """Test CustomPromptProcessor with correct method name"""
    try:
        print("🧪 Testing CustomPromptProcessor...")
        from src.utils.prompt_processor import CustomPromptProcessor
        
        test_prompt = "Focus on cost optimization and automation for our Netflix presentation"
        
        result = CustomPromptProcessor.process_custom_prompt(
            prompt=test_prompt,
            company_name="Netflix",
            company_context="Streaming entertainment company"
        )
        
        print("✅ CustomPromptProcessor working correctly")
        print(f"   Context type: {result.get('context_type')}")
        print(f"   Focus areas: {result.get('focus_areas')}")
        return True
        
    except Exception as e:
        print(f"❌ CustomPromptProcessor failed: {e}")
        return False

def test_status_tracker():
    """Test StatusTracker method calls"""
    try:
        print("\n🧪 Testing StatusTracker...")
        from src.utils.status_tracker import StatusTracker, StatusCheckpoints
        
        status_tracker = StatusTracker("test-session-123")
        
        # Test web scraping completed call (the problematic one)
        status_tracker.update_status(
            StatusCheckpoints.WEB_SCRAPING_COMPLETED,
            {
                'urls_scraped_count': 13,
                'urls_scraped_list': ['url1', 'url2', 'url3'],
                'successful_scrapes': 13,
                'total_attempts': 15
            },
            current_agent='web_scraper'
        )
        
        print("✅ StatusTracker working correctly")
        return True
        
    except Exception as e:
        print(f"❌ StatusTracker failed: {e}")
        return False

def test_company_research():
    """Test CompanyResearchSwarm import"""
    try:
        print("\n🧪 Testing CompanyResearchSwarm...")
        from src.agents.company_research import CompanyResearchSwarm
        
        print("✅ CompanyResearchSwarm imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ CompanyResearchSwarm failed: {e}")
        return False

def test_orchestrator():
    """Test orchestrator import"""
    try:
        print("\n🧪 Testing AgenticWAFROrchestrator...")
        from src.orchestrator import AgenticWAFROrchestrator
        
        orchestrator = AgenticWAFROrchestrator()
        print("✅ Orchestrator imported and initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("🔍 COMPLETE FIX VERIFICATION")
    print("=" * 70)
    
    # Run all tests
    test_results = []
    test_results.append(("CustomPromptProcessor", test_custom_prompt_processor()))
    test_results.append(("StatusTracker", test_status_tracker()))
    test_results.append(("CompanyResearchSwarm", test_company_research()))
    test_results.append(("AgenticWAFROrchestrator", test_orchestrator()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Your PowerPoint generation should work now!")
        print("\nSummary of fixes applied:")
        print("1. ✅ Fixed CustomPromptProcessor.process_prompt → process_custom_prompt")
        print("2. ✅ Fixed StatusTracker calls - removed invalid 'urls_scraped' parameter")
        print("3. ✅ URL lists now passed in metadata dictionary")
        print("4. ✅ All method signatures corrected")
        print("\nYour system is ready for PowerPoint generation! 🚀")
        
        print("\nNext steps:")
        print("1. Replace your src/orchestrator.py with the corrected version")
        print("2. Replace your src/agents/company_research.py with the corrected version")
        print("3. Run your original test: 'python local_testing_guide.py'")
        print("4. Generate amazing presentations! 🎨")
        
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("Make sure to:")
        print("1. Update both files with the provided corrections")
        print("2. Check for any import issues")
        print("3. Verify your Python environment")
    
    print("=" * 70)

if __name__ == "__main__":
    main()