#!/usr/bin/env python3
"""
Quick test to verify CustomPromptProcessor fix
"""
import sys
import os

# Add your src path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_custom_prompt_processor():
    """Test the CustomPromptProcessor with correct method name"""
    try:
        from src.utils.prompt_processor import CustomPromptProcessor
        
        # Test the correct method name
        test_prompt = "Focus on cost optimization and automation for our Tesla presentation"
        
        print("🧪 Testing CustomPromptProcessor...")
        print(f"Test prompt: {test_prompt}")
        
        # Call the correct method
        result = CustomPromptProcessor.process_custom_prompt(
            prompt=test_prompt,
            company_name="Tesla",
            company_context="Electric vehicle manufacturer"
        )
        
        print("\n✅ SUCCESS! CustomPromptProcessor working correctly")
        print(f"Context type: {result.get('context_type')}")
        print(f"Focus areas: {result.get('focus_areas')}")
        print(f"Processed prompt length: {len(result.get('processed_prompt', ''))}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Make sure to update your orchestrator.py file with the correct method name!")
        return False

def test_orchestrator_import():
    """Test if orchestrator can be imported after fix"""
    try:
        print("\n🔧 Testing orchestrator import...")
        from src.orchestrator import AgenticWAFROrchestrator
        orchestrator = AgenticWAFROrchestrator()
        print("✅ Orchestrator imported successfully!")
        return True
    except Exception as e:
        print(f"❌ Orchestrator import failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 TESTING CUSTOMPROMPTPROCESSOR FIX")
    print("=" * 60)
    
    # Test 1: CustomPromptProcessor method
    test1_passed = test_custom_prompt_processor()
    
    # Test 2: Orchestrator import
    test2_passed = test_orchestrator_import()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED! Your fix should work now.")
        print("\nNext steps:")
        print("1. Update src/orchestrator.py with the correct method call")
        print("2. Run your original test again")
        print("3. Generate some PowerPoint presentations!")
    else:
        print("❌ Some tests failed. Check the errors above.")
    print("=" * 60)