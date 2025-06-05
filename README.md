# MCP Search Analytics Server

A Model Context Protocol (MCP) server for Google Analytics and Search Console data analysis.

## 🚀 Features

- Unified access to Google Analytics 4 and Google Search Console data
- Real-time analytics queries through MCP interface
- Secure credential management via environment variables

## 🔧 Setup

### Prerequisites

- Python 3.8+
- Google Cloud Project with Analytics and Search Console APIs enabled
- Google Service Account with appropriate permissions

### Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd mcp-search-analytics
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

1. **Create environment file:**
   ```bash
   cp environment.example .env
   ```

2. **Set up Google Service Account:**
   - Create a service account in Google Cloud Console
   - Download the JSON credentials file
   - Enable Google Analytics Reporting API and Search Console API
   - Grant necessary permissions to your service account

3. **Configure environment variables:**
   Edit `.env` file with your actual values:
   ```
   ANALYTICS_CREDENTIALS_PATH=/path/to/your/credentials.json
   GSC_SITE_URL=https://your-website.com
   GA4_PROPERTY_ID=your-property-id
   ```

### Usage

1. Test your credentials:
```bash
python test_credentials.py
```

2. Run the MCP server:
```bash
python unified_analytics_server.py
```

## 🔐 Security Notes

- **Never commit credential files** (`.json`, `.env`) to version control
- Store credentials securely and use environment variables
- Regularly rotate service account keys
- Follow principle of least privilege for API access

## 📋 Requirements

See `requirements.txt` for Python dependencies.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license here] 