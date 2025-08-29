"""
Report generation agent for the Business Transformation Agent.
"""
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from strands import Agent, tool
from strands_tools import retrieve, http_request
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.core.bedrock_manager import EnhancedModelManager
from src.core.models import CompanyProfile, UseCaseStructured
from src.services.web_scraper import WebScraper
from src.services.aws_clients import s3_client, S3_BUCKET, LAMBDA_TMP_DIR
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import PDF generation libraries
try:
    import weasyprint
    PDF_GENERATION_AVAILABLE = True
    logger.info("✅ WeasyPrint PDF generation available")
except (ImportError, OSError) as e:
    logger.warning(f"⚠️ WeasyPrint not available: {e}")
    logger.info("🔄 Falling back to ReportLab for PDF generation")
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import black, blue, HexColor
        from reportlab.platypus.flowables import HRFlowable
        REPORTLAB_AVAILABLE = True
        PDF_GENERATION_AVAILABLE = True
        logger.info("✅ ReportLab available for PDF generation")
    except ImportError:
        REPORTLAB_AVAILABLE = False
        PDF_GENERATION_AVAILABLE = False
        logger.warning("⚠️ No PDF generation libraries available")

class ReportXMLParser:
    """Enhanced parser for converting XML tags to formatted PDF content with support for multiple formatting tags."""
    
    @staticmethod
    def parse_xml_tags(xml_content: str) -> Dict[str, Any]:
        """Parse XML-like tags from report content with comprehensive formatting support."""
        
        parsed_content = {
            'title': '',
            'sections': [],
            'citations': {},
            'inline_citations': []
        }
        
        # Extract title
        title_match = re.search(r'<heading_bold>(.*?)</heading_bold>', xml_content, re.DOTALL)
        if title_match:
            parsed_content['title'] = title_match.group(1).strip()
        
        # Extract all content sections - now includes various types
        section_patterns = [
            r'<content>(.*?)</content>',
            r'<sub-heading-bold>(.*?)</sub-heading-bold>',
            r'<sub-heading>(.*?)</sub-heading>',
            r'<section>(.*?)</section>',
            r'<paragraph>(.*?)</paragraph>',
            r'<list>(.*?)</list>',
            r'<table>(.*?)</table>'
        ]
        
        # Find all sections in order
        all_sections = []
        for pattern in section_patterns:
            matches = re.finditer(pattern, xml_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                section_type = pattern.split('(')[0].replace('<', '').replace('>', '').replace('\\', '')
                all_sections.append({
                    'type': section_type,
                    'content': match.group(1),
                    'start_pos': match.start()
                })
        
        # Sort sections by position in document
        all_sections.sort(key=lambda x: x['start_pos'])
        
        citation_counter = 1
        for section in all_sections:
            # Process citations within content
            processed_content, citation_counter = ReportXMLParser._process_inline_citations(
                section['content'], parsed_content['citations'], 
                parsed_content['inline_citations'], citation_counter
            )
            
            # Process additional formatting tags
            processed_content = ReportXMLParser._process_formatting_tags(processed_content)
            
            parsed_content['sections'].append({
                'type': section['type'],
                'content': processed_content
            })
        
        return parsed_content
    
    @staticmethod
    def _process_inline_citations(content: str, citations_dict: Dict[str, str], 
                                inline_citations: List[Dict], citation_counter: int) -> tuple:
        """Process citation tags to create inline clickable citations with enhanced distribution."""
        
        # Find citation patterns
        citation_pattern = r'<citation_name>(.*?)</citation_name><citation_url>(.*?)</citation_url>'
        matches = re.finditer(citation_pattern, content, re.DOTALL)
        
        processed_content = content
        
        for match in matches:
            citation_name = match.group(1).strip()
            citation_url = match.group(2).strip()
            
            # Skip if citation is empty or invalid
            if not citation_name or not citation_url:
                continue
            
            # Create a clean title from citation name (limit length)
            clean_title = citation_name[:50] + "..." if len(citation_name) > 50 else citation_name
            
            # Store citation for inline use
            citation_info = {
                'number': citation_counter,
                'name': clean_title,
                'url': citation_url,
                'full_name': citation_name
            }
            
            citations_dict[str(citation_counter)] = citation_info
            inline_citations.append(citation_info)
            
            # Replace with inline clickable citation with enhanced formatting
            citation_tag = f'<citation_name>{citation_name}</citation_name><citation_url>{citation_url}</citation_url>'
            inline_citation = f'<link href="{citation_url}"><u>[{citation_counter}]</u></link>'
            processed_content = processed_content.replace(citation_tag, inline_citation)
            
            citation_counter += 1
        
        return processed_content, citation_counter

    @staticmethod
    def _process_formatting_tags(content: str) -> str:
        """Process additional formatting tags like bold, italic, underline with enhanced support."""
        
        # Process bold tags
        content = re.sub(r'<bold>(.*?)</bold>', r'<b>\1</b>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process italic tags
        content = re.sub(r'<italic>(.*?)</italic>', r'<i>\1</i>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process underline tags
        content = re.sub(r'<underline>(.*?)</underline>', r'<u>\1</u>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process bullet points
        content = re.sub(r'<bullet>(.*?)</bullet>', r'• \1', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process numbered lists
        content = re.sub(r'<number>(.*?)</number>', r'1. \1', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process list containers
        content = re.sub(r'<list>(.*?)</list>', r'\1', content, flags=re.DOTALL | re.IGNORECASE)
        
        return content

class ConsolidatedReportGenerator:
    """Generate consolidated comprehensive reports with enhanced XML formatting support."""
    
    def __init__(self, model_manager: EnhancedModelManager):
        self.model_manager = model_manager
        self.web_scraper = WebScraper()
        
        self.report_agent = Agent(
            model=model_manager.research_model,

            system_prompt="""You are a professional technical writer and business strategist. Your task is to generate comprehensive business reports for transformation use cases using XML-like tags for structured formatting.

                Generate reports that are:
                - Professional and executive-ready
                - Data-driven with concrete business insights
                - Comprehensive yet focused on actionable recommendations
                - Formatted using XML tags for parsing
                - Include inline citations using <citation_name> and <citation_url> tags WITHIN content paragraphs
                - When custom context is provided, ensure all recommendations align with the specified focus areas and requirements

                MANDATORY: Talk comprehensively about ALL generated use cases, providing detailed analysis and strategic recommendations for each one.

                MANDATORY XML TAG FORMAT - Use ALL of these tags appropriately:
                
                STRUCTURAL TAGS:
                - <heading_bold>Main Report Title</heading_bold> - For the main report title
                - <sub-heading-bold>Major Section Title</sub-heading-bold> - For major section headings with bold formatting
                - <sub-heading>Section Title</sub-heading> - For section headings without bold
                - <content>Paragraph content with inline citations</content> - For main content paragraphs
                - <section>Content blocks</section> - For organizing content sections
                - <paragraph>Individual paragraph</paragraph> - For standalone paragraphs
                
                FORMATTING TAGS:
                - <bold>Bold text</bold> - For emphasizing important text
                - <italic>Italic text</italic> - For emphasis or technical terms
                - <underline>Underlined text</underline> - For highlights
                
                LIST TAGS:
                - <list>List content</list> - For organizing lists
                - <bullet>Bullet point item</bullet> - For bullet points
                - <number>Numbered item</number> - For numbered lists
                
                CITATION TAGS:
                - <citation_name>Source Name</citation_name><citation_url>https://source-url.com</citation_url> - INLINE within content
                
                EXAMPLE BETTER FORMAT FOR USE CASE OVERVIEW:
                
                <sub-heading>2.1: Identified Use Cases Overview</sub-heading>
                
                <content>Our comprehensive analysis has identified the following strategic transformation opportunities:</content>
                
                <list>
                <bullet><bold>AI-Powered Drop Prediction and Demand Forecasting</bold> - Strategic analytics for optimal inventory management</bullet>
                <bullet><bold>Hyper-Personalized Collector Experience Platform</bold> - Customer experience enhancement through personalization</bullet>
                <bullet><bold>Automated Social Media Content Generation</bold> - Automation and workflow optimization for community management</bullet>
                <bullet><bold>Intelligent Inventory Optimization</bold> - Core business optimization through supply chain automation</bullet>
                <bullet><bold>Real-Time Fan Sentiment Analysis</bold> - Data-driven decision making with market intelligence</bullet>
                <bullet><bold>Immersive AR/VR Collector Experience</bold> - Innovation acceleration through immersive technologies</bullet>
                <bullet><bold>Dynamic Pricing and Revenue Optimization</bold> - Cost optimization through intelligent pricing strategies</bullet>
                <bullet><bold>Predictive Analytics for Global Expansion</bold> - Scalability and growth enablement</bullet>
                </list>
                
                Use citations strategically throughout the document to support key claims, industry insights, and recommendations. Make citations flow naturally within the narrative.

                MANDATORY: Write detailed comprehensive analysis for EVERY use case provided. Each use case should have its own section with strategic analysis, implementation considerations, and business impact assessment using the XML formatting tags.""",
            tools=[http_request, retrieve],
            conversation_manager=SlidingWindowConversationManager(window_size=20)
        )

    def generate_consolidated_report(self, company_profile: CompanyProfile, use_cases: List[UseCaseStructured], 
                                   research_data: Dict[str, Any], session_id: str, status_tracker: StatusTracker = None,
                                   parsed_files_content: str = None, custom_context: Dict[str, str] = None) -> Optional[str]:
        """Generate consolidated PDF report with enhanced XML formatting and web scraping citations."""
        
        if status_tracker:
            status_tracker.update_status(
                StatusCheckpoints.REPORT_GENERATION_STARTED,
                {
                    'report_type': 'consolidated_comprehensive_analysis', 
                    'use_case_count': len(use_cases), 
                    'has_files': bool(parsed_files_content),
                    'has_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                    'web_citations_enabled': bool(research_data.get('web_research_data'))
                },
                current_agent='report_generator'
            )
        
        try:
            # Generate comprehensive report content with enhanced XML tags
            xml_report = self._generate_xml_report_with_enhanced_formatting(
                company_profile, use_cases, research_data, parsed_files_content, custom_context
            )
            
            # Generate and upload PDF
            pdf_url = self._generate_and_upload_pdf_from_xml(xml_report, company_profile.name, session_id)
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.REPORT_GENERATION_COMPLETED,
                    {
                        's3_url': pdf_url, 
                        'report_generated': bool(pdf_url), 
                        'content_enhanced_with_files': bool(parsed_files_content),
                        'content_aligned_with_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                        'web_citations_included': bool(research_data.get('web_research_data'))
                    }
                )
            
            return pdf_url
            
        except Exception as e:
            logger.error(f"Error generating consolidated report: {e}")
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.ERROR,
                    {'error_type': 'report_generation_error', 'error_message': str(e)}
                )
            return None

    def _generate_xml_report_with_enhanced_formatting(self, company_profile: CompanyProfile, use_cases: List[UseCaseStructured], 
                                                    research_data: Dict[str, Any], parsed_files_content: str = None,
                                                    custom_context: Dict[str, str] = None) -> str:
        """Generate XML-tagged report with enhanced formatting and comprehensive use case analysis."""
        
        # Get web research data for citations
        web_research_data = research_data.get('web_research_data', {})
        scraped_results = web_research_data.get('scraped_results', [])
        
        # Process and prepare real citations from web scraping
        real_citations = self._prepare_real_citations_from_web_scraping(scraped_results)
        
        # Web enhancement context
        web_context = ""
        if web_research_data.get('successful_scrapes', 0) > 0:
            web_context = f"""

                **Web Intelligence Integration**: This report incorporates insights from {web_research_data['successful_scrapes']} web sources discovered through Google Search and scraped using Beautiful Soup, providing current market intelligence and industry trends."""
        
        # File enhancement context
        file_context = ""
        if parsed_files_content:
            file_context = """

                **Document Analysis Integration**: This report incorporates insights from uploaded company documents, providing detailed context about current operations, processes, and strategic priorities."""
        
        # Custom context enhancement
        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""

                **Custom Context Alignment**: This analysis addresses the specified focus areas: {', '.join(custom_context.get('focus_areas', []))}. All recommendations align with the custom requirements and strategic priorities."""
        
        # Generate comprehensive XML report with enhanced formatting and real citations
        xml_prompt = f"""
                Generate a comprehensive business transformation report for **{company_profile.name}** using the FULL SET of XML-like tags for structured formatting.

                MANDATORY XML TAG STRUCTURE - Use ALL these tags appropriately:
                - <heading_bold>Main Title</heading_bold>
                - <sub-heading-bold>Major Section</sub-heading-bold>
                - <sub-heading>Section Title</sub-heading>
                - <content>Main content paragraphs with citations</content>
                - <section>Content blocks</section>
                - <paragraph>Individual paragraphs</paragraph>
                - <bold>Bold text</bold>
                - <italic>Italic text</italic>
                - <underline>Underlined text</underline>
                
                LIST TAGS:
                - <list>List container</list>
                - <bullet>Bullet point</bullet>
                - <number>Numbered item</number>
                
                CITATION TAGS:
                - <citation_name>Source Name</citation_name><citation_url>URL</citation_url>

                ### Company Context:
                - Industry: {company_profile.industry}
                - Business Model: {company_profile.business_model}
                - Company Size: {company_profile.company_size}
                - Technology Maturity: {company_profile.cloud_maturity}
                - Growth Stage: {company_profile.growth_stage}
                
                ### Research Intelligence:
                {research_data.get('research_findings', '')[:2000]}
                {web_context}
                {file_context}
                {custom_context_section}
                
                ### REAL WEB CITATIONS AVAILABLE (USE THESE THROUGHOUT THE REPORT):
                {self._format_real_citations_for_prompt(real_citations)}
                
                ### MANDATORY: Comprehensive Analysis of ALL {len(use_cases)} Transformation Use Cases:
                {self._format_all_use_cases_for_comprehensive_analysis(use_cases)}

                ### MANDATORY XML REPORT STRUCTURE WITH ENHANCED FORMATTING AND REAL CITATIONS:

                <heading_bold>GenAI Transformation Strategy for {company_profile.name}</heading_bold>

                <content>The convergence of <bold>{company_profile.name}'s</bold> comprehensive business operations and rapidly advancing GenAI technologies presents a transformational opportunity to revolutionize their industry position. With organizations in the <italic>{company_profile.industry}</italic> sector achieving <bold>15-65% improvements</bold> in key metrics through AI implementations {self._get_citation_tag(real_citations, 0)}, {company_profile.name}'s strong foundation and strategic positioning create ideal conditions for high-impact AI adoption.</content>

                <sub-heading-bold>Section 1: Strategic Context and Business Position</sub-heading-bold>

                <content><bold>{company_profile.name}</bold> operates as a premier organization in the <italic>{company_profile.industry}</italic> sector, with significant opportunities for technology-enabled transformation. Recent expansion and strategic positioning align with industry transformation trends {self._get_citation_tag(real_citations, 1)}, representing substantial operational scale requiring sophisticated technological solutions.</content>

                <sub-heading>1.1: Market Dynamics and Transformation Imperative</sub-heading>

                <content>The <italic>{company_profile.industry}</italic> sector faces accelerating digital pressure that GenAI can uniquely address. Market volatility creates operational challenges throughout value chains {self._get_citation_tag(real_citations, 2)}, while technology infrastructure complexities strain traditional operational methods. Industry analysis shows that {company_profile.industry} companies are increasingly adopting AI-driven solutions to maintain competitive advantage {self._get_citation_tag(real_citations, 3)}.</content>

                <sub-heading-bold>Section 2: Comprehensive Use Case Portfolio Analysis</sub-heading-bold>

                <content>Our analysis has identified <bold>{len(use_cases)} strategic transformation initiatives</bold> specifically designed for {company_profile.name}'s operational context. Each use case addresses core business challenges while building capabilities for sustained competitive advantage {self._get_citation_tag(real_citations, 4)}. These initiatives are based on industry best practices and proven transformation methodologies {self._get_citation_tag(real_citations, 5)}.</content>

                <sub-heading>2.1: Identified Use Cases Overview</sub-heading>

                <content>Our comprehensive analysis has identified the following strategic transformation opportunities:</content>

                <list>
                {self._format_use_cases_as_bullet_list(use_cases)}
                </list>

                <sub-heading-bold>Section 3: Detailed Use Case Analysis</sub-heading-bold>

                [MANDATORY: Now generate a comprehensive detailed section for EACH use case with enhanced formatting and real citations:]

                [FOR EACH USE CASE, CREATE THIS STRUCTURE WITH REAL CITATIONS:]

                <sub-heading>3.X: Use Case - [USE CASE TITLE]</sub-heading>

                <content><bold>Strategic Overview</bold>: [Detailed analysis with key points and <italic>strategic importance</italic>] {self._get_citation_tag(real_citations, 6)}</content>

                <paragraph><bold>Current State Assessment</bold>: [Current situation analysis] Industry research indicates that similar challenges affect {company_profile.industry} organizations {self._get_citation_tag(real_citations, 7)}.</paragraph>

                <paragraph><bold>Proposed Transformation Solution</bold>: [Detailed solution with <underline>technical components</underline>] This approach leverages proven methodologies {self._get_citation_tag(real_citations, 8)} and cutting-edge technologies to deliver measurable business outcomes.</paragraph>

                <list>
                <bullet><bold>Technology Architecture</bold>: AWS services implementation</bullet>
                <bullet><bold>Business Value</bold>: Quantified impact and ROI</bullet>
                <bullet><bold>Implementation Strategy</bold>: Phased approach</bullet>
                <bullet><bold>Success Metrics</bold>: KPIs and performance indicators</bullet>
                </list>

                <paragraph>This initiative aligns with industry best practices for <italic>{company_profile.industry}</italic> transformation {self._get_citation_tag(real_citations, 9)} and positions {company_profile.name} for competitive advantage.</paragraph>

                [Continue this pattern for ALL {len(use_cases)} use cases - DO NOT SKIP ANY - USE REAL CITATIONS THROUGHOUT]

                <sub-heading-bold>Section 4: Implementation Roadmap and Strategic Recommendations</sub-heading-bold>

                <content><bold>Success requires disciplined execution</bold> focusing on quick wins while building capabilities for transformational applications. The phased approach minimizes business disruption while maximizing value creation {self._get_citation_tag(real_citations, 10)}. Industry research demonstrates that organizations following structured implementation methodologies achieve 40-60% better outcomes {self._get_citation_tag(real_citations, 11)}.</content>

                <sub-heading>4.1: Priority Implementation Sequence</sub-heading>

                <list>
                <number><bold>Phase 1</bold>: Foundation and Quick Wins</number>
                <number><bold>Phase 2</bold>: Core Transformation Initiatives</number>
                <number><bold>Phase 3</bold>: Advanced Capabilities</number>
                <number><bold>Phase 4</bold>: Innovation and Optimization</number>
                </list>

                <sub-heading-bold>Section 5: Conclusion and Strategic Imperatives</sub-heading-bold>

                <content><bold>{company_profile.name}'s operational readiness</bold>, market opportunity, and technology maturity create optimal conditions for GenAI transformation delivering substantial annual value. The combination of operational efficiency gains, cost reductions, and revenue enhancements positions GenAI as a <underline>strategic imperative</underline> rather than optional technology upgrade {self._get_citation_tag(real_citations, 12)}. Industry analysis confirms that early adopters of GenAI technologies gain significant competitive advantages {self._get_citation_tag(real_citations, 13)}.</content>

                CRITICAL REQUIREMENTS:
                1. Use ALL XML formatting tags consistently throughout the report
                2. Embed REAL citations naturally within content using citation name/URL tag pairs
                3. Use the provided real web citations throughout the document - DO NOT use generic citations
                4. Create professional, consulting-grade document with rich formatting
                5. Include specific quantified metrics and strategic recommendations
                6. Focus on business value and transformation impact
                7. MANDATORY: Write comprehensive analysis for EVERY single use case with enhanced formatting
                8. Use section numbering and logical organization
                9. Apply formatting tags to emphasize key points effectively
                10. Each use case should have its own detailed section with strategic analysis
                11. Format the use cases overview as a properly formatted bullet list with bold titles and descriptions
                12. DISTRIBUTE REAL CITATIONS THROUGHOUT THE ENTIRE DOCUMENT - use them in every major section
                13. Make citations flow naturally within the narrative - don't just add them at the end of sentences

                Generate a comprehensive report that demonstrates deep industry knowledge and provides detailed strategic analysis for ALL {len(use_cases)} transformation use cases using the complete XML formatting structure and REAL web citations throughout.
            """

        try:
            response = self.report_agent(xml_prompt)
            xml_content = str(response).strip()
            
            logger.info(f"Generated enhanced XML report with real citations: {len(xml_content)} characters")
            return xml_content
            
        except Exception as e:
            logger.error(f"Error generating XML report: {e}")
            return self._create_fallback_xml_report_with_enhanced_formatting(
                company_profile, use_cases, research_data, parsed_files_content, custom_context, scraped_results
            )

    def _prepare_real_citations_from_web_scraping(self, scraped_results: List[Dict]) -> List[Dict]:
        """Prepare real citations from web scraping results."""
        real_citations = []
        
        if not scraped_results:
            # Fallback citations if no web scraping results
            fallback_citations = [
                {'name': 'McKinsey Digital Transformation Research', 'url': 'https://www.mckinsey.com/capabilities/mckinsey-digital'},
                {'name': 'Deloitte Technology Transformation', 'url': 'https://www.deloitte.com/global/en/services/consulting/services/technology-transformation.html'},
                {'name': 'AWS Digital Transformation Guide', 'url': 'https://aws.amazon.com/digital-transformation/'},
                {'name': 'PwC Digital Strategy Framework', 'url': 'https://www.pwc.com/us/en/services/consulting/digital-strategy.html'},
                {'name': 'BCG Digital Transformation', 'url': 'https://www.bcg.com/capabilities/digital-technology-data/digital-transformation'},
                {'name': 'Gartner Technology Trends', 'url': 'https://www.gartner.com/en/topics/technology-trends'},
                {'name': 'Forrester Digital Transformation', 'url': 'https://www.forrester.com/report-category/digital-transformation/'},
                {'name': 'IDC Technology Research', 'url': 'https://www.idc.com/getdoc.jsp?containerId=prUS48907623'},
                {'name': 'Accenture Technology Vision', 'url': 'https://www.accenture.com/us-en/insights/technology/technology-trends-2024'},
                {'name': 'KPMG Digital Transformation', 'url': 'https://home.kpmg/xx/en/home/insights/2020/04/digital-transformation.html'},
                {'name': 'EY Technology Consulting', 'url': 'https://www.ey.com/en_us/technology-consulting'},
                {'name': 'Bain Digital Transformation', 'url': 'https://www.bain.com/insights/topics/digital-transformation/'},
                {'name': 'Strategy& Digital Strategy', 'url': 'https://www.strategyand.pwc.com/gx/en/unique-solutions/digital-transformation.html'},
                {'name': 'Capgemini Digital Innovation', 'url': 'https://www.capgemini.com/services/digital-innovation/'}
            ]
            return fallback_citations
        
        # Process real scraped results
        for result in scraped_results:
            if result.get('success') and result.get('url') and result.get('title'):
                # Clean and validate the citation
                title = result.get('title', '').strip()
                url = result.get('url', '').strip()
                
                # Skip if title is too short or URL is invalid
                if len(title) < 10 or not url.startswith('http'):
                    continue
                
                # Clean title (remove common prefixes)
                title = re.sub(r'^(Home|About|Contact|Services|Products)\s*[-|]?\s*', '', title)
                
                # Limit title length
                if len(title) > 80:
                    title = title[:77] + "..."
                
                real_citations.append({
                    'name': title,
                    'url': url,
                    'full_name': result.get('title', title)
                })
        
        # If we don't have enough real citations, add some fallbacks
        if len(real_citations) < 5:
            fallback_citations = [
                {'name': 'McKinsey Digital Transformation Research', 'url': 'https://www.mckinsey.com/capabilities/mckinsey-digital'},
                {'name': 'Deloitte Technology Transformation', 'url': 'https://www.deloitte.com/global/en/services/consulting/services/technology-transformation.html'},
                {'name': 'AWS Digital Transformation Guide', 'url': 'https://aws.amazon.com/digital-transformation/'}
            ]
            real_citations.extend(fallback_citations)
        
        return real_citations

    def _format_real_citations_for_prompt(self, real_citations: List[Dict]) -> str:
        """Format real citations for the prompt."""
        if not real_citations:
            return "No real citations available - using fallback citations"
        
        citations_text = "REAL WEB CITATIONS TO USE THROUGHOUT THE REPORT:\n"
        for i, citation in enumerate(real_citations[:15], 1):  # Limit to first 15
            citations_text += f"{i}. {citation['name']} - {citation['url']}\n"
        
        return citations_text

    def _get_citation_tag(self, real_citations: List[Dict], index: int) -> str:
        """Get a citation tag for use in the XML content."""
        if not real_citations or index >= len(real_citations):
            # Return empty string if no citations available
            return ""
        
        citation = real_citations[index % len(real_citations)]
        return f'<citation_name>{citation["name"]}</citation_name><citation_url>{citation["url"]}</citation_url>'

    def _format_use_cases_as_bullet_list(self, use_cases: List[UseCaseStructured]) -> str:
        """Format use cases as a properly formatted bullet list with bold titles and descriptions."""
        bullet_list = []
        
        for uc in use_cases:
            # Create a clean bullet point with bold title and description
            bullet_point = f'<bullet><bold>{uc.title}</bold> - {uc.category}: {uc.business_value}</bullet>'
            bullet_list.append(bullet_point)
        
        return '\n'.join(bullet_list)

    def _format_available_citations(self, scraped_results: List[Dict]) -> str:
        """Format available citations for the prompt."""
        if not scraped_results:
            return "No web citations available"
        
        citations = []
        for i, result in enumerate(scraped_results[:10], 1):  # Limit to first 10
            if result.get('success') and result.get('url'):
                title = result.get('title', 'Web Source')[:60]
                url = result.get('url')
                citations.append(f"{i}. {title} - {url}")
        
        return "Available web citations:\n" + "\n".join(citations) if citations else "No valid citations available"

    def _format_all_use_cases_for_comprehensive_analysis(self, use_cases: List[UseCaseStructured]) -> str:
        """Format ALL use cases for comprehensive analysis in the XML report prompt."""
        formatted_cases = []
        
        for i, uc in enumerate(use_cases, 1):
            formatted_cases.append(f"""
            {i}. **{uc.title}**
               - Category: {uc.category}
               - Current State: {uc.current_state}
               - Proposed Solution: {uc.proposed_solution}
               - Business Value: {uc.business_value}
               - AWS Services: {', '.join(uc.primary_aws_services)}
               - Implementation Phases: {', '.join(uc.implementation_phases)}
               - Timeline: {uc.timeline_months} months
               - Monthly Cost: \${uc.monthly_cost_usd}
               - Priority: {uc.priority}
               - Complexity: {uc.complexity}
               - Risk Level: {uc.risk_level}
               - Success Metrics: {', '.join(uc.success_metrics)}
            """)
        
        return f"""
        COMPREHENSIVE USE CASE ANALYSIS REQUIRED FOR ALL {len(use_cases)} INITIATIVES:
        
        {chr(10).join(formatted_cases)}
        
        MANDATORY: Each use case listed above MUST have its own detailed section in the report with comprehensive strategic analysis, technical considerations, business impact assessment, and implementation recommendations using enhanced XML formatting.
        """

    def _create_fallback_xml_report_with_enhanced_formatting(self, company_profile: CompanyProfile, 
                                                           use_cases: List[UseCaseStructured],
                                                           research_data: Dict[str, Any], 
                                                           parsed_files_content: str = None,
                                                           custom_context: Dict[str, str] = None, 
                                                           scraped_results: List[Dict] = None) -> str:
        """Create fallback XML report with enhanced formatting and comprehensive use case analysis."""
        
        enhancement_notes = []
        if research_data.get('web_research_data', {}).get('successful_scrapes', 0) > 0:
            enhancement_notes.append(f"Enhanced with Web Intelligence from {research_data['web_research_data']['successful_scrapes']} sources")
        if parsed_files_content:
            enhancement_notes.append("Enhanced with Document Analysis")
        if custom_context and custom_context.get('processed_prompt'):
            enhancement_notes.append(f"Aligned with Custom Context ({custom_context.get('context_type', 'general')})")
        
        enhancement = f" ({', '.join(enhancement_notes)})" if enhancement_notes else ""
        
        # Get citation URLs from scraped results or use enhanced fallback citations
        citations = self._prepare_real_citations_from_web_scraping(scraped_results) if scraped_results else []
        
        # Generate properly formatted use case bullet list
        use_case_bullets = self._format_use_cases_as_bullet_list(use_cases)
        
        # Generate comprehensive use case sections with enhanced formatting and better citation distribution
        use_case_sections = []
        for i, uc in enumerate(use_cases, 1):
            # Use different citations for different aspects of each use case
            citation_ref = citations[i % len(citations)] if citations else citations[0] if citations else None
            citation_1 = citations[(i * 2) % len(citations)] if citations else citations[0] if citations else None
            citation_2 = citations[(i * 3) % len(citations)] if citations else citations[1] if citations else None
            citation_3 = citations[(i * 4) % len(citations)] if citations else citations[2] if citations else None
            
            # Create citation tags
            citation_tag = self._get_citation_tag(citations, i) if citations else ""
            citation_tag_1 = self._get_citation_tag(citations, i * 2) if citations else ""
            citation_tag_2 = self._get_citation_tag(citations, i * 3) if citations else ""
            citation_tag_3 = self._get_citation_tag(citations, i * 4) if citations else ""
            
            use_case_section = f"""
                <sub-heading>3.{i}: Use Case - {uc.title}</sub-heading>

                <content><bold>Strategic Overview</bold>: <italic>{uc.title}</italic> represents a critical transformation initiative for {company_profile.name}, addressing fundamental business challenges through strategic technology adoption. This initiative aligns with industry best practices for <italic>{company_profile.industry}</italic> transformation {citation_tag} and positions the organization for competitive advantage.</content>

                <paragraph><bold>Current State Assessment</bold>: {uc.current_state} This situation creates <underline>operational inefficiencies</underline> and limits {company_profile.name}'s ability to scale effectively. Industry analysis shows that organizations facing similar challenges experience 20-40% operational inefficiencies {citation_tag_1}.</paragraph>

                <paragraph><bold>Proposed Transformation Solution</bold>: {uc.proposed_solution} This comprehensive approach leverages <italic>proven methodologies</italic> and cutting-edge technologies to deliver measurable business outcomes {citation_tag_2}.</paragraph>

                <list>
                <bullet><bold>Technology Architecture</bold>: Utilizes {', '.join(uc.primary_aws_services)} as core components</bullet>
                <bullet><bold>Business Value</bold>: {uc.business_value} with ROI of 200-400% within 18-24 months</bullet>
                <bullet><bold>Implementation Timeline</bold>: {uc.timeline_months}-month phased approach</bullet>
                <bullet><bold>Monthly Investment</bold>: <underline>${uc.monthly_cost_usd:,}</underline> operational cost</bullet>
                </list>

                <paragraph><bold>Implementation Strategy</bold>: The {uc.timeline_months}-month implementation follows a phased approach: {', '.join(uc.implementation_phases)}. This methodology minimizes business disruption while maximizing value realization {citation_tag_3}.</paragraph>

                <paragraph><bold>Success Metrics and KPIs</bold>: Success will be measured through {', '.join(uc.success_metrics)}, providing clear performance indicators and accountability mechanisms. These metrics align with industry standards for <italic>{company_profile.industry}</italic> transformation initiatives.</paragraph>

                <paragraph><bold>Risk Assessment</bold>: With a {uc.risk_level} risk profile and <italic>{uc.complexity} complexity level</italic>, this initiative requires careful planning and execution. Mitigation strategies include comprehensive testing, stakeholder engagement, and phased rollout approaches.</paragraph>
            """
                    
            use_case_sections.append(use_case_section)
            
            # Combine all sections into the full report with enhanced formatting and better citation distribution
            full_report = f"""<heading_bold>GenAI Transformation Strategy for {company_profile.name}{enhancement}</heading_bold>

                <content>The convergence of <bold>{company_profile.name}'s</bold> comprehensive operations and rapidly advancing GenAI technologies presents a transformational opportunity to revolutionize their position in the <italic>{company_profile.industry}</italic> sector. With organizations achieving <bold>15-65% improvements</bold> in key metrics through GenAI implementations {self._get_citation_tag(citations, 0)}, {company_profile.name}'s strong foundation creates ideal conditions for high-impact AI adoption.</content>

                <sub-heading-bold>Section 1: Strategic Context and Business Position</sub-heading-bold>

                <content><bold>{company_profile.name}</bold> operates as a premier organization in the <italic>{company_profile.industry}</italic> sector, with significant opportunities for technology-enabled transformation {self._get_citation_tag(citations, 1)}. Their established market presence and operational expertise provide the foundation necessary for comprehensive GenAI deployment.</content>

                <sub-heading>1.1: Market Dynamics and Transformation Imperative</sub-heading>

                <content>The <italic>{company_profile.industry}</italic> sector faces accelerating digital pressure that GenAI can uniquely address. Market volatility creates operational challenges throughout value chains {self._get_citation_tag(citations, 2)}, while technology infrastructure complexities strain traditional operational methods. Industry research indicates that early adopters of AI technologies gain significant competitive advantages {self._get_citation_tag(citations, 3)}.</content>

                <sub-heading-bold>Section 2: Comprehensive Use Case Portfolio Analysis</sub-heading-bold>

                <content>Our analysis has identified <bold>{len(use_cases)} strategic transformation initiatives</bold> specifically designed for {company_profile.name}'s operational context. Each use case addresses core business challenges while building capabilities for sustained competitive advantage {self._get_citation_tag(citations, 4)}. These initiatives are based on industry best practices and proven transformation methodologies {self._get_citation_tag(citations, 5)}.</content>

                <sub-heading>2.1: Identified Use Cases Overview</sub-heading>

                <content>Our comprehensive analysis has identified the following strategic transformation opportunities:</content>

                <list>
                {use_case_bullets}
                </list>

                <sub-heading-bold>Section 3: Detailed Use Case Analysis</sub-heading-bold>

                {''.join(use_case_sections)}

                <sub-heading-bold>Section 4: Implementation Roadmap and Strategic Recommendations</sub-heading-bold>

                <content><bold>Success requires disciplined execution</bold> focusing on quick wins while building capabilities for transformational applications. The phased approach minimizes business disruption while maximizing value creation {self._get_citation_tag(citations, 10)}. Industry research demonstrates that organizations following structured implementation methodologies achieve 40-60% better outcomes {self._get_citation_tag(citations, 11)}.</content>

                <sub-heading>4.1: Priority Implementation Sequence</sub-heading>

                <list>
                <number><bold>Phase 1</bold>: Foundation and Quick Wins (Months 1-3)</number>
                <number><bold>Phase 2</bold>: Core Transformation Initiatives (Months 4-9)</number>
                <number><bold>Phase 3</bold>: Advanced Capabilities (Months 10-15)</number>
                <number><bold>Phase 4</bold>: Innovation and Optimization (Months 16-18)</number>
                </list>

                <sub-heading-bold>Section 5: Conclusion and Strategic Imperatives</sub-heading-bold>

                <content><bold>{company_profile.name}'s operational readiness</bold>, market opportunity, and technology maturity create optimal conditions for GenAI transformation delivering substantial annual value. The combination of operational efficiency gains, cost reductions, and revenue enhancements positions GenAI as a <underline>strategic imperative</underline> rather than optional technology upgrade {self._get_citation_tag(citations, 12)}. Industry analysis confirms that early adopters of GenAI technologies gain significant competitive advantages {self._get_citation_tag(citations, 13)}. The <bold>{len(use_cases)} strategic initiatives</bold> outlined in this report provide a comprehensive roadmap for transformation success.</content>
            """
        
        return full_report

    def _generate_and_upload_pdf_from_xml(self, xml_content: str, company_name: str, session_id: str) -> Optional[str]:
        """Generate PDF from enhanced XML content and upload to S3."""
        
        try:
            # Parse XML content with enhanced formatting support
            parsed_content = ReportXMLParser.parse_xml_tags(xml_content)
            
            # Create temp directory
            tmp_dir = os.path.join(LAMBDA_TMP_DIR, session_id)
            os.makedirs(tmp_dir, exist_ok=True)
            
            pdf_filename = os.path.join(tmp_dir, f"transformation_report_{session_id}.pdf")
            
            if REPORTLAB_AVAILABLE:
                # Use ReportLab to create professional PDF with enhanced formatting
                self._create_professional_pdf_with_enhanced_formatting(parsed_content, pdf_filename, company_name)
                logger.info(f"✅ Enhanced PDF generated using ReportLab: {pdf_filename}")
                
            else:
                logger.error("❌ No PDF generation libraries available")
                return None
            
            # Verify PDF was created
            if not os.path.exists(pdf_filename) or os.path.getsize(pdf_filename) == 0:
                logger.error("❌ PDF file was not created or is empty")
                return None
            
            # Upload to S3
            s3_url = self._upload_pdf_to_s3(pdf_filename, session_id, company_name)
            
            # Cleanup
            try:
                if os.path.exists(pdf_filename):
                    os.unlink(pdf_filename)
            except Exception as e:
                logger.warning(f"Failed to cleanup PDF file: {e}")
            
            return s3_url
            
        except Exception as e:
            logger.error(f"❌ Enhanced PDF generation failed: {e}")
            return None

    def _create_professional_pdf_with_enhanced_formatting(self, parsed_content: Dict[str, Any], pdf_filename: str, company_name: str):
        """Create professional PDF using ReportLab with enhanced formatting support."""
        
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import black, blue, HexColor
        from reportlab.platypus.flowables import HRFlowable
        
        # Create PDF document
        doc = SimpleDocTemplate(
            pdf_filename, 
            pagesize=A4,
            rightMargin=0.75*inch, 
            leftMargin=0.75*inch,
            topMargin=0.75*inch, 
            bottomMargin=0.75*inch
        )
        
        # Get base styles
        styles = getSampleStyleSheet()
        
        # Create enhanced custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Title'],
            fontSize=22,
            spaceAfter=30,
            spaceBefore=20,
            textColor=HexColor('#2C3E50'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=26
        )
        
        # Enhanced heading styles
        main_heading_style = ParagraphStyle(
            'MainHeading',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            spaceBefore=28,
            textColor=HexColor('#34495E'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=20
        )
        
        sub_heading_bold_style = ParagraphStyle(
            'SubHeadingBold',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=18,
            spaceBefore=24,
            textColor=HexColor('#2C3E50'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=18
        )
        
        sub_heading_style = ParagraphStyle(
            'SubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=14,
            spaceBefore=18,
            textColor=HexColor('#34495E'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=16
        )
        
        # Enhanced content styles
        content_style = ParagraphStyle(
            'ContentText',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            spaceBefore=6,
            alignment=4,  # Justified
            textColor=black,
            fontName='Helvetica',
            leading=16,
            leftIndent=0,
            rightIndent=0
        )
        
        paragraph_style = ParagraphStyle(
            'ParagraphText',
            parent=content_style,
            fontSize=11,
            spaceAfter=10,
            spaceBefore=4,
            alignment=4,
            leading=15
        )
        
        # List styles
        bullet_style = ParagraphStyle(
            'BulletText',
            parent=content_style,
            fontSize=11,
            spaceAfter=6,
            spaceBefore=3,
            leftIndent=20,
            bulletIndent=10,
            leading=14
        )
        
        # Build story
        story = []
        
        # Add title
        title = parsed_content.get('title', f'GenAI Transformation Strategy for {company_name}')
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Add horizontal rule
        story.append(HRFlowable(width="100%", thickness=2, color=HexColor('#3498DB')))
        story.append(Spacer(1, 20))
        
        # Process content sections with enhanced formatting
        for section in parsed_content.get('sections', []):
            if section.get('content', '').strip():
                section_type = section.get('type', 'content')
                section_content = section.get('content', '')
                
                # Clean content for PDF and enhance inline citations
                cleaned_content = self._enhance_inline_citations_for_pdf(
                    section_content, 
                    parsed_content.get('citations', {})
                )
                
                # Apply appropriate style based on section type
                if section_type == 'heading_bold':
                    story.append(Paragraph(cleaned_content, main_heading_style))
                elif section_type == 'sub-heading-bold':
                    story.append(Paragraph(cleaned_content, sub_heading_bold_style))
                elif section_type == 'sub-heading':
                    story.append(Paragraph(cleaned_content, sub_heading_style))
                elif section_type == 'paragraph':
                    story.append(Paragraph(cleaned_content, paragraph_style))
                elif section_type == 'content':
                    story.append(Paragraph(cleaned_content, content_style))
                elif section_type == 'list':
                    # Process list items within the list
                    list_items = [item.strip() for item in cleaned_content.split('•') if item.strip()]
                    for item in list_items:
                        if item:
                            story.append(Paragraph(f"• {item}", bullet_style))
                else:
                    # Default to content style
                    story.append(Paragraph(cleaned_content, content_style))
                
                story.append(Spacer(1, 8))
        
        # Add citation summary section
        citations = parsed_content.get('citations', {})
        if citations:
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#BDC3C7')))
            story.append(Spacer(1, 15))
            story.append(Paragraph("Citation Sources", sub_heading_bold_style))
            story.append(Spacer(1, 10))
            
            for citation_num, citation_info in citations.items():
                citation_name = citation_info.get('full_name', citation_info.get('name', 'Source'))
                citation_url = citation_info.get('url', '#')
                
                # Create reference entry
                citation_text = f'[{citation_num}] <link href="{citation_url}">{citation_url}</link>'
                story.append(Paragraph(citation_text, content_style))
                story.append(Spacer(1, 4))
        
        # Build PDF
        doc.build(story)

    def _enhance_inline_citations_for_pdf(self, content: str, citations: Dict[str, Any]) -> str:
        """Enhance inline citations and formatting tags for PDF generation with better distribution."""
        
        # Remove any remaining XML content tags
        content = re.sub(r'</?content>', '', content)
        content = re.sub(r'</?paragraph>', '', content)
        content = re.sub(r'</?section>', '', content)
        
        # Enhance existing link tags to have round appearance
        def enhance_citation_link(match):
            href = match.group(1)
            citation_num = match.group(2)
            
            # Find citation info
            citation_info = citations.get(citation_num, {})
            citation_name = citation_info.get('name', 'Source')
            
            # Create enhanced round citation with background color
            return f'<link href="{href}"><b><font face="Helvetica-Bold" size="8">&nbsp;[{citation_num}]&nbsp;</font></b></link>'
        
        # Pattern to find existing citation links
        citation_link_pattern = r'<link href="([^"]*)"><u>\[(\d+)\]</u></link>'
        content = re.sub(citation_link_pattern, enhance_citation_link, content)
        
        # Clean up extra whitespace and formatting
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Ensure proper spacing around citations
        content = re.sub(r'(\w)\[(\d+)\]', r'\1 [\2]', content)
        content = re.sub(r'\[(\d+)\](\w)', r'[\1] \2', content)
        
        return content

    def _upload_pdf_to_s3(self, pdf_path: str, session_id: str, company_name: str) -> Optional[str]:
        """Upload PDF to S3 and return object URL."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"transformation-reports/{session_id}/comprehensive-analysis/{timestamp}_transformation_report.pdf"
            
            # Upload to S3
            s3_client.upload_file(
                pdf_path,
                S3_BUCKET,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf',
                    'Metadata': {
                        'session_id': session_id,
                        'company_name': company_name,
                        'report_type': 'comprehensive_transformation_analysis_with_enhanced_formatting',
                        'generated_at': timestamp
                    }
                }
            )
            
            # Generate object URL
            s3_object_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"✅ Enhanced PDF uploaded to S3: {s3_key}")
            return s3_object_url
            
        except Exception as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return None
