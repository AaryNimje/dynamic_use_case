"""
Main orchestrator for the Business Transformation Agent with complete PowerPoint support.
"""
import logging
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Any, List, Optional

from strands import Agent

from src.agents.company_research import CompanyResearchSwarm
from src.agents.report_generator import ConsolidatedReportGenerator
from src.agents.use_case_generator import DynamicUseCaseGenerator, OutputParser
from src.agents.multi_template_ppt_generator import MultiTemplatePPTGenerator
from src.core.bedrock_manager import EnhancedModelManager
from src.core.models import CompanyProfile, UseCase, CompanyInfo
from src.services.web_scraper import WEB_SCRAPING_AVAILABLE
from src.utils.cache_manager import CacheManager
from src.utils.file_parser import FileParser
from src.utils.prompt_processor import CustomPromptProcessor
from src.utils.session_manager import SessionManager
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenticWAFROrchestrator:
    """Enhanced orchestrator with web scraping, custom prompt processing, file parsing, personalized use case generation, comprehensive reporting, and multi-template PowerPoint presentation generation."""

    def __init__(self): 
        self.model_manager = EnhancedModelManager()
        self.research_swarm = CompanyResearchSwarm(self.model_manager)
        self.dynamic_use_case_generator = DynamicUseCaseGenerator(self.model_manager)
        self.consolidated_report_generator = ConsolidatedReportGenerator(self.model_manager)
        self.multi_ppt_generator = MultiTemplatePPTGenerator(self.model_manager)
        self.session_store = {}

        # Add session manager for duplicate prevention
        self.session_manager = SessionManager()

        # Business analysis extractor agent
        self.profile_extractor = Agent(
            model=self.model_manager.research_model,
            system_prompt="""You are a Senior Business Intelligence Analyst specializing in extracting actionable company insights.
                Analyze the provided business research data and extract key company information for strategic transformation planning. Focus on practical business context that enables strategic decision-making and transformation initiatives.

                When web-scraped content is provided, use it as primary market intelligence.
                When document content is provided, use it as internal operational intelligence.
                When custom context or specific requirements are provided, ensure analysis aligns with those priorities and focus areas.

                Extract insights about:
                - Core business operations and value creation
                - Strategic challenges and growth opportunities  
                - Technology readiness and transformation capacity
                - Market position and competitive dynamics
                - Specific operational processes and departments mentioned
                - Geographic markets and regulatory context
                - Team size and organizational structure implications
             """
        )
        logger.info("✅ Orchestrator Initialized with PPT support")

    def process_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process transformation request with web scraping, custom prompt, file parsing, personalized use case generation, consolidated reporting, and PowerPoint presentations."""
        try:
            company_name = payload.get('company_name', '').strip()
            company_url = payload.get('company_url', '').strip()
            session_id = payload.get('session_id', str(uuid.uuid4()))
            action = payload.get('action', 'start')
            selected_use_case_ids = payload.get('selected_use_case_ids', [])
            project_id = payload.get('project_id', 'default_project')
            user_id = payload.get('user_id', 'default_user')
            files = payload.get('files', [])  # S3 URLs to PDF/DOCX files
            custom_prompt = payload.get('prompt', '')  # Custom prompt for additional context
            output_format = payload.get('output_format', 'pdf')  # 'pdf', 'ppt', or 'both'
            presentation_style = payload.get('presentation_style', 'first_deck')  # Template style

            if not company_name:
                return {'status': 'error', 'message': 'company_name is required'}

            # Validate output format
            valid_formats = ['pdf', 'ppt', 'both']
            if output_format not in valid_formats:
                return {
                    'status': 'error', 
                    'message': f'Invalid output_format. Must be one of: {valid_formats}'
                }

            # Validate presentation style
            valid_styles = ['first_deck', 'marketing', 'use_case', 'technical', 'strategy']
            if presentation_style not in valid_styles:
                logger.warning(f"Invalid presentation_style '{presentation_style}', using 'first_deck'")
                presentation_style = 'first_deck'

            # Initialize status tracker
            status_tracker = StatusTracker(session_id)

            # Process custom prompt if provided
            custom_context = None
            if custom_prompt:
                custom_context = CustomPromptProcessor.process_prompt(custom_prompt)
                status_tracker.update_status(
                    StatusCheckpoints.CUSTOM_PROMPT_PROCESSING,
                    {
                        'prompt_length': len(custom_prompt),
                        'context_type': custom_context.get('context_type'),
                        'focus_areas': custom_context.get('focus_areas', [])
                    }
                )
                logger.info(f"Custom prompt processed: {custom_context.get('context_type')} with {len(custom_context.get('focus_areas', []))} focus areas")

            # Handle different actions
            if action == 'start':
                return self._handle_start(company_name, company_url, session_id, status_tracker, files,
                                        project_id, user_id, custom_context, output_format, presentation_style)
            
            elif action == 'select_use_cases':
                return self._handle_select_use_cases(company_name, company_url, selected_use_case_ids,
                                                   session_id, status_tracker, output_format, presentation_style)
            
            elif action == 'fetch':
                return self._handle_fetch(company_name, company_url, payload.get('fetch_type', 'all'))

            else:
                return {
                    'status': 'error',
                    'message': f'Invalid action: {action}. Valid actions: start, select_use_cases, fetch',
                    'valid_actions': ['start', 'select_use_cases', 'fetch'],
                    'valid_formats': valid_formats,
                    'valid_styles': valid_styles
                }

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'message': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            }

    def _handle_start(self, company_name: str, company_url: str, session_id: str, status_tracker: StatusTracker,
                      files: List[str], project_id: str, user_id: str, custom_context: Optional[Dict[str, str]] = None,
                      output_format: str = "pdf", presentation_style: str = "first_deck") -> Dict[str, Any]:
        """Handle start action with PDF and PowerPoint generation support."""
        
        logger.info(
            f"Starting transformation process for {company_name} with {len(files)} files, custom context: {bool(custom_context)}, output format: {output_format}, presentation style: {presentation_style}, and web scraping enabled: {WEB_SCRAPING_AVAILABLE}")

        # Parse uploaded files if provided
        parsed_files_content = None
        logger.info(f"✅ File: files: {files}")
        if files:
            parsed_files_content = self._parse_uploaded_files(files, status_tracker)

        logger.info(f"✅ File files parsed_files_content: {parsed_files_content}")
        
        # Conduct comprehensive business research
        research_data = self.research_swarm.conduct_comprehensive_research(
            company_name, company_url, status_tracker, parsed_files_content, custom_context
        )

        # Update status for agent analysis
        status_tracker.update_status(
            StatusCheckpoints.AGENT_ANALYZING,
            {
                'phase': 'company_profile_extraction',
                'enhanced_with_files': bool(parsed_files_content),
                'enhanced_with_custom_context': bool(custom_context),
                'enhanced_with_web_scraping': bool(research_data.get('web_research_data'))
            },
            current_agent='profile_extractor'
        )

        # Extract business-focused company profile
        company_profile = self._extract_company_profile(company_name, company_url, research_data,
                                                        parsed_files_content, custom_context)

        # Generate transformation use cases
        structured_use_cases = self.dynamic_use_case_generator.generate_dynamic_use_cases(
            company_profile, research_data, status_tracker, parsed_files_content, custom_context
        )

        # Cache the generated use cases
        CacheManager.save_use_cases_to_cache(session_id, structured_use_cases)

        # Initialize output URLs
        report_url = None
        presentation_url = None

        # Generate outputs based on format
        if output_format in ['pdf', 'both']:
            # Generate PDF report
            status_tracker.update_status(
                StatusCheckpoints.REPORT_GENERATION_STARTED,
                {'format': 'pdf', 'company': company_name}
            )
            
            report_url = self.consolidated_report_generator.generate_consolidated_report(
                company_profile, structured_use_cases, research_data, session_id, status_tracker,
                parsed_files_content, custom_context
            )

        if output_format in ['ppt', 'both']:
            # Generate PowerPoint presentation
            status_tracker.update_status(
                StatusCheckpoints.TEMPLATE_SELECTED,
                {
                    'template': presentation_style,
                    'company': company_name,
                    'format': 'ppt'
                }
            )
            
            presentation_url = self.multi_ppt_generator.generate_presentation(
                company_profile, structured_use_cases, research_data, session_id, 
                status_tracker, presentation_style
            )

        # Final status update
        status_tracker.update_status(
            StatusCheckpoints.COMPLETED,
            {
                'total_use_cases': len(structured_use_cases),
                'output_format': output_format,
                'presentation_style': presentation_style if output_format in ['ppt', 'both'] else None,
                'pdf_generated': bool(report_url),
                'ppt_generated': bool(presentation_url),
                'enhanced_with_files': bool(parsed_files_content),
                'enhanced_with_custom_context': bool(custom_context),
                'enhanced_with_web_scraping': bool(research_data.get('web_research_data'))
            }
        )

        # Prepare response
        response = {
            'status': 'completed',
            'session_id': session_id,
            'company_name': company_name,
            'company_url': company_url,
            'total_use_cases': len(structured_use_cases),
            'use_cases': [asdict(uc) for uc in structured_use_cases[:5]],
            'output_format': output_format,
            'presentation_style': presentation_style if output_format in ['ppt', 'both'] else None,
            'message': self._get_completion_message(output_format, report_url, presentation_url),
            'research_metadata': {
                'method': research_data.get('method', 'standard'),
                'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
                'total_urls_processed': research_data.get('web_research_data', {}).get('total_urls_processed', 0),
                'successful_web_scrapes': research_data.get('web_research_data', {}).get('successful_scrapes', 0),
                'enhanced_with_files': bool(parsed_files_content),
                'enhanced_with_custom_context': bool(custom_context)
            },
            'custom_context_summary': custom_context,
            'timestamp': datetime.now().isoformat()
        }

        # Add output URLs
        if report_url:
            response['report_url'] = report_url
        if presentation_url:
            response['presentation_url'] = presentation_url

        return response

    def _handle_select_use_cases(self, company_name: str, company_url: str, selected_use_case_ids: List[str],
                                 session_id: str, status_tracker: StatusTracker, output_format: str = "pdf", 
                                 presentation_style: str = "first_deck") -> Dict[str, Any]:
        """Handle use case selection with PowerPoint support."""
        
        logger.info(f"Processing selected use cases for {company_name}")

        # Get cached use cases
        cached_use_cases = CacheManager.get_use_cases_from_cache(session_id)
        if not cached_use_cases:
            return {
                'status': 'error',
                'message': 'No cached use cases found. Please run start action first.',
                'session_id': session_id
            }

        # Filter selected use cases
        selected_use_cases = []
        for uc in cached_use_cases:
            if uc.id in selected_use_case_ids:
                selected_use_cases.append(uc)

        if not selected_use_cases:
            return {
                'status': 'error',
                'message': 'No valid use cases found for the provided IDs',
                'available_ids': [uc.id for uc in cached_use_cases]
            }

        # Get cached company profile and research data
        company_profile = CacheManager.get_company_profile_from_cache(session_id)
        research_data = CacheManager.get_research_data_from_cache(session_id)

        if not company_profile or not research_data:
            return {
                'status': 'error',
                'message': 'Missing cached data. Please run start action first.',
                'session_id': session_id
            }

        # Initialize output URLs
        report_url = None
        presentation_url = None

        # Generate outputs based on format
        if output_format in ['pdf', 'both']:
            # Generate PDF report with selected use cases
            report_url = self.consolidated_report_generator.generate_consolidated_report(
                company_profile, selected_use_cases, research_data, session_id, status_tracker
            )

        if output_format in ['ppt', 'both']:
            # Generate PowerPoint presentation with selected use cases
            presentation_url = self.multi_ppt_generator.generate_presentation(
                company_profile, selected_use_cases, research_data, session_id, 
                status_tracker, presentation_style
            )

        # Prepare response
        response = {
            'status': 'completed',
            'session_id': session_id,
            'company_name': company_name,
            'selected_use_cases': len(selected_use_cases),
            'output_format': output_format,
            'presentation_style': presentation_style if output_format in ['ppt', 'both'] else None,
            'message': self._get_completion_message(output_format, report_url, presentation_url),
            'timestamp': datetime.now().isoformat()
        }

        # Add output URLs
        if report_url:
            response['report_url'] = report_url
        if presentation_url:
            response['presentation_url'] = presentation_url

        return response

    def _handle_fetch(self, company_name: str, company_url: str, fetch_type: str = 'all') -> Dict[str, Any]:
        """Handle fetch action with PowerPoint context."""
        
        if fetch_type == 'use_cases':
            use_cases_result = CacheManager.get_cached_use_cases_by_company(company_name, company_url)
            return use_cases_result

        elif fetch_type == 'outputs':
            outputs_result = CacheManager.get_cached_outputs_by_company(company_name, company_url)
            return outputs_result

        elif fetch_type == 'sessions':
            sessions_result = CacheManager.get_cached_sessions_by_company(company_name, company_url)
            return sessions_result

        elif fetch_type == 'all':
            # Get all cached data for the company
            use_cases_result = CacheManager.get_cached_use_cases_by_company(company_name, company_url)
            outputs_result = CacheManager.get_cached_outputs_by_company(company_name, company_url)
            all_sessions = CacheManager.get_cached_sessions_by_company(company_name, company_url).get('sessions', [])

            if use_cases_result.get('status') == 'found_cached_use_cases' or outputs_result.get('status') == 'found_cached_outputs':
                return {
                    'status': 'found_cached_data',
                    'company_name': company_name,
                    'company_url': company_url,
                    'total_sessions': len(all_sessions),
                    'use_cases_status': use_cases_result.get('status'),
                    'outputs_status': outputs_result.get('status'),
                    'detailed_use_cases': use_cases_result if use_cases_result.get('status') == 'found_cached_use_cases' else None,
                    'detailed_outputs': outputs_result if outputs_result.get('status') == 'found_cached_outputs' else None,
                    'latest_session': all_sessions[0] if all_sessions else None,
                    'message': f"Retrieved all cached data for {company_name} ({len(all_sessions)} sessions) with PDF and PowerPoint outputs",
                    'available_actions': ['start', 'select_use_cases'],
                    'available_formats': ['pdf', 'ppt', 'both'],
                    'available_styles': ['first_deck', 'marketing', 'use_case', 'technical', 'strategy'],
                    'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
                    'timestamp': datetime.now().isoformat()
                }

        return {
            'status': 'no_cached_data',
            'company_name': company_name,
            'company_url': company_url,
            'message': f'No cached data found for {company_name}',
            'suggestion': 'Use action: "start" with output_format: "pdf", "ppt", or "both"',
            'available_actions': ['start'],
            'available_formats': ['pdf', 'ppt', 'both'],
            'available_styles': ['first_deck', 'marketing', 'use_case', 'technical', 'strategy'],
            'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }

    def _get_completion_message(self, output_format: str, report_url: str, presentation_url: str) -> str:
        """Generate completion message based on output format and generation success."""
        
        if output_format == 'both':
            pdf_status = "PDF report available" if report_url else "PDF generation failed"
            ppt_status = "PowerPoint presentation available" if presentation_url else "PowerPoint generation failed"
            return f"Generated both {pdf_status.lower()} and {ppt_status.lower()}."
        elif output_format == 'ppt':
            return f"Generated PowerPoint presentation{' ready for download and editing' if presentation_url else ' generation failed'}."
        else:
            return f"Generated PDF report{' with comprehensive analysis' if report_url else ' generation failed'}."

    def _generate_cache_key_for_company(self, company_name: str, company_url: str) -> str:
        """Generate cache key for company lookup."""
        return CacheManager.generate_cache_key({
            'company_name': company_name,
            'company_url': company_url,
            'action': 'start'
        })

    def _parse_uploaded_files(self, files: List[str], status_tracker: StatusTracker) -> Optional[str]:
        """Parse uploaded S3 files and return combined content."""
        
        if not files:
            return None

        status_tracker.update_status(
            StatusCheckpoints.FILE_PARSING_STARTED,
            {'total_files': len(files)},
            current_agent='file_parser'
        )

        try:
            combined_content = ""
            parsed_count = 0

            for file_url in files:
                try:
                    content = FileParser.parse_s3_file(file_url)
                    if content:
                        combined_content += f"\n\n--- Document {parsed_count + 1} ---\n{content}"
                        parsed_count += 1
                except Exception as e:
                    logger.error(f"Failed to parse file {file_url}: {e}")

            status_tracker.update_status(
                StatusCheckpoints.FILE_PARSING_COMPLETED,
                {
                    'total_files': len(files),
                    'parsed_files': parsed_count,
                    'content_length': len(combined_content)
                },
                current_agent='file_parser'
            )

            logger.info(f"Successfully parsed {parsed_count}/{len(files)} files")
            return combined_content if combined_content.strip() else None

        except Exception as e:
            logger.error(f"Error parsing uploaded files: {e}")
            status_tracker.update_status(
                StatusCheckpoints.ERROR,
                {'error': str(e), 'phase': 'file_parsing'}
            )
            return None

    def _extract_company_profile(self, company_name: str, company_url: str, research_data: Dict[str, Any],
                                 parsed_files_content: str = None,
                                 custom_context: Dict[str, str] = None) -> CompanyProfile:
        """Extract structured company profile from business research with error handling."""
        
        # Handle null research_data
        if research_data is None:
            research_data = {}
        
        web_context = ""
        web_research_data = research_data.get('web_research_data', {})
        if web_research_data and web_research_data.get('research_content'):
            web_context = f"""
            
WEB INTELLIGENCE ANALYSIS:
Based on web scraping of {web_research_data.get('successful_scrapes', 0)} sources:

{web_research_data['research_content'][:2000]}

Use this market intelligence to understand their competitive position and industry context.
            """

        file_context = ""
        if parsed_files_content:
            file_context = f"""
            
COMPANY DOCUMENT ANALYSIS:
The following content was extracted from company documents:

{parsed_files_content[:2000]}

Use this as primary intelligence to understand their actual operations.
            """

        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""
            
CUSTOM CONTEXT REQUIREMENTS:
{custom_context['processed_prompt'][:1000]}

Focus Areas: {', '.join(custom_context.get('focus_areas', []))}
            """

        extraction_prompt = f"""
        Extract strategic business profile from comprehensive research data:
        
        COMPANY: {company_name}
        URL: {company_url}
        
        BUSINESS RESEARCH DATA:
        {research_data.get('research_findings', 'Standard business analysis')[:2000]}
        {web_context}
        {file_context}
        {custom_context_section}
        
        Analyze and extract key business intelligence based on the provided context.
        """

        try:
            response = self.profile_extractor(extraction_prompt)
            response_text = str(response)
            return OutputParser.parse_company_profile(response_text, company_name)

        except Exception as e:
            logger.error(f"Error extracting business profile: {e}")
            return OutputParser.parse_company_profile("", company_name)