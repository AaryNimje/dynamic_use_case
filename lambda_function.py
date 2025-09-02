"""
Bare minimum Lambda handler with PPT support.
"""

# 🔧 Set EFS package path FIRST, before any imports
import sys
sys.path.insert(0, "/mnt/efs/envs/strands_lambda/lambda-env")

# ✅ Now safely import everything else
import json
import logging
import traceback
from datetime import datetime

# Local imports (which depend on pdfplumber, PyPDF2, etc.)
from src.orchestrator import AgenticWAFROrchestrator
from src.utils.cache_manager import CacheManager
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    """
    AWS Lambda handler with web scraping, custom prompt processing, file parsing, 
    personalized transformation, caching, status tracking, consolidated report generation,
    and PowerPoint presentation support.
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        # Log prompt and files if available
        if body.get('prompt'):
            logger.info(f"Custom prompt provided: {len(body['prompt'])} characters")
        
        if body.get('files'):
            logger.info(f"Files provided: {len(body['files'])} files")

        # Log output format and presentation style if available
        if body.get('output_format'):
            logger.info(f"Output format requested: {body['output_format']}")

        if body.get('presentation_style'):
            logger.info(f"Presentation style requested: {body['presentation_style']}")

        # Add validation for output format
        valid_output_formats = ['pdf', 'ppt', 'both']
        if body.get('output_format') and body['output_format'] not in valid_output_formats:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': f'Invalid output_format. Must be one of: {valid_output_formats}',
                    'valid_formats': valid_output_formats,
                    'provided_format': body.get('output_format'),
                    'timestamp': datetime.now().isoformat()
                })
            }

        # Add validation for presentation style
        valid_presentation_styles = ['executive', 'technical', 'marketing', 'strategy']
        if body.get('presentation_style') and body['presentation_style'] not in valid_presentation_styles:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': f'Invalid presentation_style. Must be one of: {valid_presentation_styles}',
                    'valid_styles': valid_presentation_styles,
                    'provided_style': body.get('presentation_style'),
                    'timestamp': datetime.now().isoformat()
                })
            }

        # Handle polling action
        if body.get('action') == 'fetch' and body.get('fetch_type') == 'status':
            session_id = body.get('session_id')
            if session_id:
                status_tracker = StatusTracker(session_id)
                current_status = status_tracker.get_current_status()
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps({
                        'status': 'status_retrieved',
                        'session_id': session_id,
                        'current_status': current_status,
                        'timestamp': datetime.now().isoformat(),
                        'polling_recommended': current_status.get('current_status') not in [
                            StatusCheckpoints.COMPLETED,
                            StatusCheckpoints.ERROR,
                            StatusCheckpoints.USE_CASES_GENERATED,
                            StatusCheckpoints.REPORT_GENERATION_COMPLETED,
                            StatusCheckpoints.PPT_GENERATION_COMPLETED
                        ]
                    }, default=str)
                }

        # Generate and check cache
        cache_key = CacheManager.generate_cache_key(body)
        if body.get('action') != 'fetch' or body.get('fetch_type') != 'status':
            cached_result = CacheManager.get_from_cache(cache_key)
            if cached_result:
                logger.info(f"Returning cached result for key: {cache_key}")
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps(cached_result, default=str)
                }

        # Run orchestrator
        logger.info(f"Cache miss for key: {cache_key}, processing transformation request with output format: {body.get('output_format', 'pdf')}")
        orchestrator = AgenticWAFROrchestrator()
        result = orchestrator.process_request(body)

        # Cache result (but not status polls)
        if body.get('action') != 'fetch' or body.get('fetch_type') != 'status':
            CacheManager.save_to_cache(cache_key, body, result)

        # Log successful completion with format info
        if result.get('status') in ['use_cases_generated', 'completed']:
            output_format = result.get('output_format', 'pdf')
            report_url = result.get('report_url')
            presentation_url = result.get('presentation_url')
            
            success_message = f"Successfully processed request with {output_format} output:"
            if output_format == 'both':
                success_message += f" PDF {'✅' if report_url else '❌'}, PPT {'✅' if presentation_url else '❌'}"
            elif output_format == 'ppt':
                success_message += f" PPT {'✅' if presentation_url else '❌'}"
            else:
                success_message += f" PDF {'✅' if report_url else '❌'}"
            
            logger.info(success_message)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        logger.error(traceback.format_exc())
        
        # Enhanced error response with format context
        error_context = {}
        try:
            if isinstance(event.get('body'), str):
                body = json.loads(event['body'])
            else:
                body = event.get('body', event)
            
            if body.get('output_format'):
                error_context['requested_output_format'] = body['output_format']
            if body.get('presentation_style'):
                error_context['requested_presentation_style'] = body['presentation_style']
        except:
            pass
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'message': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat(),
                **error_context
            })
        }