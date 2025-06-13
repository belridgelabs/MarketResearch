# Government Contracting Sales Helper

This simple Python script generates a one-pager summarizing publicly available information about a government contact. It searches the web, pulls content from the top results, and uses the OpenAI API to distill the information.

## Requirements

- Python 3.8+
- `requests`
- `beautifulsoup4`
- `openai`

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Set your OpenAI API key in the environment:

```bash
export OPENAI_API_KEY=your-key-here
```

Then run the script with the individual's name and agency:

```bash
python gov_contract_sales_app.py "Jane Doe" "Department of Energy"
```

The program will search DuckDuckGo, scrape the top results, and ask the OpenAI API to generate a one-pager summarizing what you should know before the call.
