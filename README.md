# Government Contract Sales Research App

A Python application that generates comprehensive one-pagers for government contracting sales calls. The app researches individuals and their agencies using web scraping, LinkedIn data, and specialized government contracting sources like FedScoop and OrangeSlices, then creates both console output and formatted PDF reports.

## Features

- **Multi-source Research**: Combines data from DuckDuckGo search, OpenAI, and Perplexity AI
- **Government Focus**: Specialized research for federal agencies and contractors
- **AI-Powered Review System**: 
  - **Review Agent**: Uses Perplexity's Sonar Pro to fact-check and evaluate summary completeness
  - **Writer Agent**: Iteratively improves summaries based on review feedback
  - **Quality Assurance**: Ensures summaries are factually accurate and comprehensive enough for sales calls
- **PDF Generation**: Creates professional, formatted PDF reports using Playwright and Tailwind CSS
- **Duplicate Detection**: Automatically removes redundant information
- **Professional Formatting**: Clean, readable output optimized for sales preparation

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd MarketResearch
```

2. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

3. Install Playwright browser binaries:
```bash
playwright install chromium
```

4. Set up environment variables:
Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_openai_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here
```

## Usage

### Basic Usage
```bash
python3 gov_contract_sales_app.py "John Doe" "Department of Defense"
```

### Multi-word Agency Names
```bash
python3 gov_contract_sales_app.py "Jane Smith" "Department of Homeland Security"
```

### Output
The application will:
1. Display research results in the console
2. Generate a formatted PDF report (e.g., `sales_report_John_Doe_Department_of_Defense.pdf`)

## PDF Report Features

The generated PDF reports include:
- **Professional Header**: Contact name, agency, and generation timestamp
- **Tailwind CSS Styling**: Modern, clean design with proper typography
- **Key Information Section**: Organized bullet points with relevant sales insights
- **Responsive Layout**: Optimized for A4 printing with proper margins
- **Branded Footer**: Identifies the generation tool

## Testing

Run the test script to verify PDF generation:
```bash
python3 test_pdf_generation.py
```

This will create a `sample_sales_report.pdf` with sample data.

## Dependencies

- `beautifulsoup4`: HTML parsing for web scraping
- `openai`: OpenAI API integration
- `playwright`: Browser automation for PDF generation
- `python-dotenv`: Environment variable management
- `requests`: HTTP requests for web scraping

## API Requirements

- **OpenAI API Key**: For AI-powered research and summary generation
- **Perplexity API Key**: For enhanced search capabilities with search results

### Perplexity Search Results Format
Perplexity responses now include a `search_results` array with objects containing:
- `title`: page title
- `url`: link to the result
- `date`: publication date
These links are appended beneath the scraped content for full traceability.

## File Structure

```
MarketResearch/
├── .env                              # Environment variables (create this)
├── .gitignore                        # Git ignore rules
├── README.md                         # This file
├── gov_contract_sales_app.py         # Main application
├── requirements.txt                  # Python dependencies
├── test_pdf_generation.py           # PDF generation test script
└── .trae/
    └── rules/
        └── project_rules.md          # Project guidelines
```

## Example Output

The application generates both console output and PDF reports:

### Console Output
```
=== SALES CALL PREPARATION: John Doe at Department of Defense ===

1. 15+ years of experience in cybersecurity and government contracting
2. Currently serves as Deputy Director of IT Security
3. Led implementation of zero-trust architecture across 12 federal agencies
...

📄 PDF report generated: sales_report_John_Doe_Department_of_Defense.pdf
```

### PDF Report
A professionally formatted document with:
- Header with contact information and timestamp
- Organized key points in an easy-to-read format
- Modern styling with Tailwind CSS
- Print-ready layout

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure `.env` file contains valid API keys
2. **Playwright Installation**: Run `playwright install chromium` if PDF generation fails
3. **Network Issues**: Check internet connection for web scraping functionality
4. **Permission Errors**: Ensure write permissions in the project directory

### Error Messages

- `❌ Failed to generate PDF report`: Check Playwright installation
- `⚠️ No summary available to generate PDF`: Verify API keys and network connectivity
- `OPENAI_API_KEY not set`: Add API key to `.env` file

## Contributing

When contributing to this project:
1. Follow existing code style and patterns
2. Test both console output and PDF generation
3. Update documentation for new features
4. Ensure all dependencies are listed in `requirements.txt`

## License

This project is for educational and professional use in government contracting sales preparation.

