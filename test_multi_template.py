#!/usr/bin/env python3
"""
Test script for the Multi-Template PowerPoint Generation System
"""
import os

def test_template_system():
    """Test the multi-template PPT generation system"""
    
    print("Multi-Template PowerPoint Generator Test")
    print("=" * 40)
    
    # Import the system
    try:
        from multi_template_ppt_generator import MultiTemplatePPTGenerator, TEMPLATE_REGISTRY
        print("✓ Multi-template system imported successfully")
        print(f"✓ Available templates: {list(TEMPLATE_REGISTRY.keys())}")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure multi_template_ppt_generator.py is in the same directory")
        return
    
    # Get PDF file path
    print("\nEnter the full path to your PDF file:")
    print("Example: C:\\Users\\YourName\\Documents\\business_report.pdf")
    pdf_path = input("PDF Path: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"✗ File not found: {pdf_path}")
        return
    
    # Get company name
    company_name = input("\nCompany name (optional): ").strip()
    if not company_name:
        company_name = None
    
    # Choose template type
    print("\nAvailable Presentation Templates:")
    templates = {
        "1": ("first_deck", "First Deck Call - High-level executive overview"),
        "2": ("marketing", "Marketing Presentation - Persuasive, benefit-focused"),
        "3": ("use_case", "Use Case Scenarios - Detailed problem-solution-benefit"),
        "4": ("technical", "Technical Architecture - Specifications and implementation"),
        "5": ("strategy", "Strategy Planning - Roadmaps and strategic initiatives")
    }
    
    for key, (template_id, description) in templates.items():
        print(f"{key}. {description}")
    
    choice = input("\nChoose template (1-5): ").strip()
    
    if choice not in templates:
        print("Invalid choice. Using first_deck template.")
        template_type = "first_deck"
    else:
        template_type, description = templates[choice]
        print(f"Selected: {description}")
    
    try:
        # Initialize generator
        generator = MultiTemplatePPTGenerator()
        
        print(f"\nGenerating {template_type} presentation...")
        print("This may take 60-90 seconds for analysis and generation...")
        
        # Generate presentation
        result = generator.generate_presentation(
            pdf_path=pdf_path,
            template_type=template_type,
            company_name=company_name
        )
        
        # Show results
        file_size = os.path.getsize(result)
        abs_path = os.path.abspath(result)
        
        print(f"\n✓ SUCCESS!")
        print(f"Generated: {result}")
        print(f"Template: {template_type}")
        print(f"Size: {file_size:,} bytes")
        print(f"Location: {abs_path}")
        print(f"\nOpen in PowerPoint, Google Slides, or any presentation software")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_all_templates():
    """Test generation with all template types using the same PDF"""
    
    print("Testing All Template Types")
    print("=" * 30)
    
    # Get PDF path
    pdf_path = input("Enter PDF file path for testing all templates: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    company_name = input("Company name (optional): ").strip() or None
    
    try:
        from multi_template_ppt_generator import MultiTemplatePPTGenerator, TEMPLATE_REGISTRY
        
        generator = MultiTemplatePPTGenerator()
        results = []
        
        print(f"\nGenerating presentations with all {len(TEMPLATE_REGISTRY)} templates...")
        
        for template_type in TEMPLATE_REGISTRY.keys():
            print(f"\n--- Generating {template_type} presentation ---")
            
            try:
                result = generator.generate_presentation(
                    pdf_path=pdf_path,
                    template_type=template_type,
                    company_name=company_name
                )
                
                file_size = os.path.getsize(result)
                results.append((template_type, result, file_size))
                print(f"✓ {template_type}: {result} ({file_size:,} bytes)")
                
            except Exception as e:
                print(f"✗ {template_type} failed: {e}")
        
        print(f"\n" + "=" * 50)
        print(f"GENERATION COMPLETE!")
        print(f"Successfully created {len(results)} presentations:")
        
        for template_type, filename, size in results:
            print(f"  • {template_type}: {filename} ({size:,} bytes)")
        
        return results
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def create_templates():
    """Create template files"""
    
    print("Creating Template Files")
    print("=" * 25)
    
    try:
        from create_template_files import main as create_templates_main
        create_templates_main()
    except ImportError:
        print("Template creator not found. Make sure create_template_files.py is available.")

def main():
    """Main test menu"""
    
    print("Multi-Template PowerPoint Generator Test Suite")
    print("=" * 50)
    
    while True:
        print("\nTest Options:")
        print("1. Test single template generation")
        print("2. Test all templates with same PDF")
        print("3. Create template files")
        print("4. Exit")
        
        choice = input("\nChoose option (1-4): ").strip()
        
        if choice == "1":
            test_template_system()
        elif choice == "2":
            test_all_templates()
        elif choice == "3":
            create_templates()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    main()