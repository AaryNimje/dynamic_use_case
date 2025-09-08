#!/usr/bin/env python3
"""
Test the PDF content to PowerPoint generation system
"""
import os

def test_system():
    """Test PDF content to PPT generation"""
    
    print("PDF Content to PowerPoint Test")
    print("=" * 30)
    
    # Import the system
    try:
        from pdf_content_to_ppt import PDFtoPPTSystem
        print("System imported successfully")
    except ImportError as e:
        print(f"Import failed: {e}")
        print("Make sure pdf_content_to_ppt.py is in the same directory")
        return
    
    # Get PDF path
    pdf_path = input("Enter PDF file path: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    # Get company name
    company = input("Company name (optional): ").strip()
    
    try:
        # Initialize system
        system = PDFtoPPTSystem()
        
        print("\nGenerating PowerPoint presentation...")
        print("This will take 30-60 seconds...")
        
        # Generate PPT
        result = system.generate_ppt_from_pdf(
            pdf_path=pdf_path,
            company_name=company if company else None,
            template="executive"
        )
        
        print(f"\nSuccess! Generated: {result}")
        print(f"File size: {os.path.getsize(result):,} bytes")
        print(f"Location: {os.path.abspath(result)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_system()