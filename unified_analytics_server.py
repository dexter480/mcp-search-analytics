#!/usr/bin/env python3
"""
Unified Google Analytics MCP Server - MINIMAL MULTI-SITE CHANGES
Only modified the parts needed to support both sites
"""

import json
import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
)

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv not installed. Run: pip install python-dotenv")
    def load_dotenv():
        pass

class UnifiedAnalyticsMCPServer:
    def __init__(self, credentials_path: str):
        """
        Initialize the Unified Analytics MCP Server
        
        Args:
            credentials_path: Path to Google service account JSON file
        """
        self.credentials_path = credentials_path
        
        # CHANGE 1: Read both sites from environment variables
        self.sites = {
            'vesivanov': {
                'gsc_url': os.environ.get('GSC_SITE_URL', 'sc-domain:vesivanov.com'),
                'ga4_property_id': os.environ.get('GA4_PROPERTY_ID', '487808497')
            },
            'mebelcenter': {
                'gsc_url': os.environ.get('MEBELCENTER_GSC_URL', 'sc-domain:mebelcenter.bg'),
                'ga4_property_id': os.environ.get('MEBELCENTER_GA4_PROPERTY_ID')
            }
        }
        
        # Validate that we have both sites configured
        if not self.sites['mebelcenter']['ga4_property_id']:
            print("[ERROR] MEBELCENTER_GA4_PROPERTY_ID environment variable is required", file=sys.stderr)
            sys.exit(1)
        
        self.gsc_service = None
        self.ga4_client = None
        self.server = Server("unified-analytics-mcp-server")
        
        # Setup MCP handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available analytics tools"""
            return [
                # GSC Tools - CHANGE 2: Add site parameter to all tools
                Tool(
                    name="gsc_search_analytics",
                    description="Get Google Search Console search analytics data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                            "dimensions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Dimensions to group by (query, page, country, device, searchAppearance)"
                            },
                            "row_limit": {"type": "integer", "description": "Maximum rows (default 1000)", "default": 1000}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                Tool(
                    name="gsc_top_queries",
                    description="Get top performing search queries from GSC",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                            "limit": {"type": "integer", "description": "Number of queries (default 50)", "default": 50}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                
                # GA4 Tools - CHANGE 2: Add site parameter to all tools
                Tool(
                    name="ga4_traffic_overview",
                    description="Get GA4 traffic overview with key metrics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                Tool(
                    name="ga4_top_pages",
                    description="Get top performing pages from GA4",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                            "metric": {
                                "type": "string",
                                "enum": ["sessions", "screenPageViews", "totalUsers"],
                                "description": "Metric to sort by",
                                "default": "screenPageViews"
                            },
                            "limit": {"type": "integer", "description": "Number of pages", "default": 20}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                Tool(
                    name="ga4_acquisition_report",
                    description="Get GA4 traffic acquisition data by source/medium",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                            "limit": {"type": "integer", "description": "Number of sources", "default": 25}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                
                # Combined Analysis Tools - CHANGE 2: Add site parameter
                Tool(
                    name="combined_performance_report",
                    description="Combined GSC + GA4 performance analysis for a date range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                Tool(
                    name="page_analysis",
                    description="Analyze specific page performance across GSC and GA4",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "enum": ["vesivanov", "mebelcenter"],
                                "description": "Which site to analyze: vesivanov or mebelcenter",
                                "default": "vesivanov"
                            },
                            "page_path": {"type": "string", "description": "Page path to analyze (e.g., '/blog/article')"},
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
                        },
                        "required": ["page_path", "start_date", "end_date"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            await self._ensure_services_initialized()
            
            try:
                if name == "gsc_search_analytics":
                    result = await self._gsc_search_analytics(**arguments)
                elif name == "gsc_top_queries":
                    result = await self._gsc_top_queries(**arguments)
                elif name == "ga4_traffic_overview":
                    result = await self._ga4_traffic_overview(**arguments)
                elif name == "ga4_top_pages":
                    result = await self._ga4_top_pages(**arguments)
                elif name == "ga4_acquisition_report":
                    result = await self._ga4_acquisition_report(**arguments)
                elif name == "combined_performance_report":
                    result = await self._combined_performance_report(**arguments)
                elif name == "page_analysis":
                    result = await self._page_analysis(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
            except Exception as e:
                error_msg = f"Error in {name}: {str(e)}"
                print(f"[ERROR] {error_msg}", file=sys.stderr)
                return [TextContent(type="text", text=error_msg)]
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available analytics resources"""
            resources = []
            for site in ['vesivanov', 'mebelcenter']:
                for period, description in [
                    ("today", "Today's Analytics Dashboard"),
                    ("yesterday", "Yesterday's Analytics Dashboard"),
                    ("week", "Weekly Analytics Dashboard"),
                    ("month", "Monthly Analytics Dashboard")
                ]:
                    resources.append(
                        Resource(
                            uri=f"analytics://dashboard/{period}/{site}",
                            name=f"{description} - {site.title()}",
                            description=f"Complete analytics overview for {site} - {period}",
                            mimeType="application/json"
                        )
                    )
            return resources
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read analytics resources"""
            
            await self._ensure_services_initialized()
            
            try:
                today = datetime.now().date()
                
                # Parse URI: analytics://dashboard/period/site
                parts = uri.split('/')
                if len(parts) < 5:
                    raise ValueError(f"Invalid resource URI format: {uri}")
                
                period = parts[3]
                site = parts[4]
                
                # Calculate date range
                if period == "today":
                    start_date = end_date = today.isoformat()
                elif period == "yesterday":
                    yesterday = today - timedelta(days=1)
                    start_date = end_date = yesterday.isoformat()
                elif period == "week":
                    start_date = (today - timedelta(days=7)).isoformat()
                    end_date = today.isoformat()
                elif period == "month":
                    start_date = (today - timedelta(days=30)).isoformat()
                    end_date = today.isoformat()
                else:
                    raise ValueError(f"Unknown period: {period}")
                
                result = await self._combined_performance_report(
                    site=site,
                    start_date=start_date,
                    end_date=end_date
                )
                
                return json.dumps(result, indent=2)
                
            except Exception as e:
                error_msg = f"Error reading resource {uri}: {str(e)}"
                print(f"[ERROR] {error_msg}", file=sys.stderr)
                return json.dumps({"error": error_msg})
    
    async def _ensure_services_initialized(self):
        """Ensure both GSC and GA4 services are initialized"""
        if not self.gsc_service or not self.ga4_client:
            await self._initialize_services()
    
    async def _initialize_services(self):
        """Initialize both GSC and GA4 services with shared credentials"""
        try:
            print(f"[INFO] Initializing services with credentials from: {self.credentials_path}")
            
            # Load credentials with both scopes
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/webmasters.readonly',
                    'https://www.googleapis.com/auth/analytics.readonly'
                ]
            )
            
            # Initialize GSC service
            self.gsc_service = build('searchconsole', 'v1', credentials=credentials)
            print("[SUCCESS] GSC service initialized")
            
            # Initialize GA4 client
            self.ga4_client = BetaAnalyticsDataClient(credentials=credentials)
            print("[SUCCESS] GA4 client initialized")
            
        except Exception as e:
            error_msg = f"Failed to initialize services: {str(e)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise Exception(error_msg)
    
    # CHANGE 3: Modify methods to accept site parameter and use site config
    async def _gsc_search_analytics(self, start_date: str, end_date: str, 
                                   site: str = "vesivanov",
                                   dimensions: Optional[List[str]] = None,
                                   row_limit: int = 1000) -> Dict[str, Any]:
        """Get GSC search analytics data"""
        
        # CHANGE 3a: Get site-specific URL
        site_url = self.sites[site]['gsc_url']
        
        request_body = {
            'startDate': start_date,
            'endDate': end_date,
            'rowLimit': row_limit
        }
        
        if dimensions:
            request_body['dimensions'] = dimensions
        
        try:
            request = self.gsc_service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            )
            response = request.execute()
            
            return {
                'source': 'Google Search Console',
                'site': site,
                'site_url': site_url,
                'date_range': f"{start_date} to {end_date}",
                'total_rows': len(response.get('rows', [])),
                'dimensions': dimensions or [],
                'data': response.get('rows', [])
            }
            
        except HttpError as e:
            raise Exception(f"GSC API error: {str(e)}")
    
    async def _gsc_top_queries(self, start_date: str, end_date: str, 
                              site: str = "vesivanov", limit: int = 50) -> Dict[str, Any]:
        """Get top queries from GSC"""
        return await self._gsc_search_analytics(
            start_date=start_date,
            end_date=end_date,
            site=site,
            dimensions=['query'],
            row_limit=limit
        )
    
    # GA4 Methods - CHANGE 3: Add site parameter
    async def _ga4_run_report(self, dimensions: List[str], metrics: List[str], 
                             start_date: str, end_date: str, 
                             site: str = "vesivanov", limit: int = 100) -> Dict[str, Any]:
        """Run a GA4 report"""
        
        # CHANGE 3b: Get site-specific property ID
        property_id = self.sites[site]['ga4_property_id']
        
        try:
            request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                limit=limit
            )
            
            response = self.ga4_client.run_report(request=request)
            
            rows = []
            for row in response.rows:
                row_data = {}
                
                for i, dim_value in enumerate(row.dimension_values):
                    dim_name = dimensions[i] if i < len(dimensions) else f"dimension_{i}"
                    row_data[dim_name] = dim_value.value
                
                for i, metric_value in enumerate(row.metric_values):
                    metric_name = metrics[i] if i < len(metrics) else f"metric_{i}"
                    row_data[metric_name] = metric_value.value
                
                rows.append(row_data)
            
            return {
                'source': 'Google Analytics 4',
                'site': site,
                'property_id': property_id,
                'date_range': f"{start_date} to {end_date}",
                'dimensions': dimensions,
                'metrics': metrics,
                'row_count': len(rows),
                'data': rows
            }
        except Exception as e:
            raise Exception(f"GA4 API error: {str(e)}")
    
    async def _ga4_traffic_overview(self, start_date: str, end_date: str, 
                                   site: str = "vesivanov") -> Dict[str, Any]:
        """Get GA4 traffic overview"""
        metrics = [
            "sessions", "totalUsers", "newUsers", "screenPageViews", 
            "bounceRate", "averageSessionDuration", "sessionsPerUser"
        ]
        
        result = await self._ga4_run_report([], metrics, start_date, end_date, site, 1)
        
        if result['data']:
            overview = result['data'][0]
            result['overview'] = overview
            del result['data']
        
        return result
    
    async def _ga4_top_pages(self, start_date: str, end_date: str, 
                            site: str = "vesivanov",
                            metric: str = "screenPageViews", limit: int = 20) -> Dict[str, Any]:
        """Get top pages from GA4"""
        dimensions = ["pagePath", "pageTitle"]
        metrics = [metric, "sessions", "totalUsers", "bounceRate"]
        
        return await self._ga4_run_report(dimensions, metrics, start_date, end_date, site, limit)
    
    async def _ga4_acquisition_report(self, start_date: str, end_date: str, 
                                     site: str = "vesivanov", limit: int = 25) -> Dict[str, Any]:
        """Get GA4 acquisition data"""
        dimensions = ["sessionSource", "sessionMedium"]
        metrics = ["sessions", "totalUsers", "newUsers", "bounceRate", "averageSessionDuration"]
        
        return await self._ga4_run_report(dimensions, metrics, start_date, end_date, site, limit)
    
    # Combined Analysis Methods - CHANGE 3: Add site parameter
    async def _combined_performance_report(self, start_date: str, end_date: str, 
                                          site: str = "vesivanov") -> Dict[str, Any]:
        """Generate combined GSC + GA4 performance report"""
        
        # Get GSC data
        gsc_data = await self._gsc_search_analytics(
            start_date=start_date,
            end_date=end_date,
            site=site,
            dimensions=['query'],
            row_limit=20
        )
        
        # Get GA4 overview
        ga4_overview = await self._ga4_traffic_overview(start_date, end_date, site)
        
        # Get top pages from GA4
        ga4_pages = await self._ga4_top_pages(start_date, end_date, site, limit=10)
        
        # Get acquisition data
        ga4_acquisition = await self._ga4_acquisition_report(start_date, end_date, site, limit=10)
        
        return {
            'report_type': 'Combined Performance Report',
            'site': site,
            'date_range': f"{start_date} to {end_date}",
            'search_console': {
                'top_queries': gsc_data.get('data', [])[:10]
            },
            'google_analytics': {
                'overview': ga4_overview.get('overview', {}),
                'top_pages': ga4_pages.get('data', [])[:5],
                'top_sources': ga4_acquisition.get('data', [])[:5]
            }
        }
    
    async def _page_analysis(self, page_path: str, start_date: str, end_date: str, 
                            site: str = "vesivanov") -> Dict[str, Any]:
        """Analyze specific page across both GSC and GA4"""
        
        # GSC data for specific page
        gsc_page_data = await self._gsc_search_analytics(
            start_date=start_date,
            end_date=end_date,
            site=site,
            dimensions=['page', 'query'],
            row_limit=100
        )
        
        # Filter for the specific page
        page_queries = [
            row for row in gsc_page_data.get('data', [])
            if len(row.get('keys', [])) > 0 and row.get('keys', [''])[0] == page_path
        ]
        
        # GA4 data for specific page
        ga4_page_data = await self._ga4_run_report(
            dimensions=["pagePath"],
            metrics=["screenPageViews", "sessions", "totalUsers", "bounceRate", "averageSessionDuration"],
            start_date=start_date,
            end_date=end_date,
            site=site,
            limit=1000
        )
        
        # Filter for the specific page
        page_analytics = [
            row for row in ga4_page_data.get('data', [])
            if row.get('pagePath') == page_path
        ]
        
        return {
            'site': site,
            'page_path': page_path,
            'date_range': f"{start_date} to {end_date}",
            'search_console': {
                'queries_count': len(page_queries),
                'top_queries': page_queries[:10]
            },
            'google_analytics': {
                'page_data': page_analytics[0] if page_analytics else None
            }
        }

async def main():
    """Main server entry point"""
    
    print("[START] Starting Unified Analytics MCP Server...")
    
    # Load environment variables from .env file
    load_dotenv()
    print("[SUCCESS] Environment variables loaded")
    
    # Configuration - get from environment variables
    credentials_path = os.environ.get('ANALYTICS_CREDENTIALS_PATH')
    
    print(f"[INFO] Credentials path: {credentials_path}")
    
    if not credentials_path:
        print("[ERROR] Error: ANALYTICS_CREDENTIALS_PATH environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(credentials_path):
        print(f"[ERROR] Error: Credentials file not found at {credentials_path}", file=sys.stderr)
        sys.exit(1)
    
    print("[SUCCESS] All configuration checks passed")
    
    # Test credentials quickly
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[
                'https://www.googleapis.com/auth/webmasters.readonly',
                'https://www.googleapis.com/auth/analytics.readonly'
            ]
        )
        print("[SUCCESS] Credentials loaded successfully")
    except Exception as e:
        print(f"[ERROR] Error loading credentials: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create and run server
    print("[INFO] Creating analytics server...")
    try:
        analytics_server = UnifiedAnalyticsMCPServer(credentials_path)
        print("[SUCCESS] Analytics server created successfully")
        print(f"[INFO] Configured sites: vesivanov, mebelcenter")
    except Exception as e:
        print(f"[ERROR] Error creating server: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run the server with proper MCP protocol
    print("[INFO] Starting MCP stdio server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            print("[SUCCESS] MCP server is running and waiting for connections...")
            print("[INFO] Server ready to receive requests from Claude Desktop")
            
            # Run the server using the correct MCP pattern
            await analytics_server.server.run(
                read_stream,
                write_stream,
                analytics_server.server.create_initialization_options()
            )
                
    except KeyboardInterrupt:
        print("[INFO] Server stopped by user")
    except Exception as e:
        print(f"[ERROR] Error running server: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[FATAL] Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)