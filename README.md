# 📈 Indian Stock Market Analyzer  

A Python toolkit that pulls Indian equity (and optional mutual‑fund) data via REST APIs, enriches it with technical & fundamental metrics, sends the cleaned payload to an external AI model, and returns OHLCV data together with AI‑generated analysis. Results are saved as JSON (machine‑readable) and Markdown reports (human‑readable).  

---  

## Table of Contents  
1. [Features](#features)  
2. [Installation](#installation)  
3. [Configuration](#configuration)  
4. [Usage](#usage)  
5. [Output](#output)  
6. [Testing](#testing)  
7. [Contributing](#contributing)  
8. [License](#license)  

---  

## Features  
- **Batch processing** of any number of ticker symbols.  
- **Resilient API client** with retries, timeouts, and rate‑limit handling.  
- Automatic calculation of **technical indicators** (SMA, EMA, RSI, MACD).  
- Computation of common **fundamental ratios** (PE, ROE, etc.) when data is available.  
- **AI‑model integration** via a POST endpoint – the model produces a free‑text summary and score.  
- Outputs **JSON** (`{ticker}.json`) for downstream pipelines and **Markdown** (`{ticker}_report.md`) for quick review.  
- Fully typed, documented, and **unit‑tested** (`pytest`).  

---  

## Installation  

```bash
# Clone the repository
git clone https://github.com/yourusername/indian-stock-analyzer.git
cd indian-stock-analyzer

# Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```  

---  

## Configuration  

The script reads API credentials from environment variables.  
Create a `.env` file in the project root (or copy the example):

```bash
cp .env.example .env
```

Edit `.env` and insert your actual keys:

```env
# Stock market data API
STOCK_API_KEY=your_stock_api_key

# AI analysis endpoint token (Bearer token)
AI_API_TOKEN=your_ai_token
```  

If you also need the Mutual‑Fund API, add its key in the same file (e.g., `MF_API_KEY`).  

---  

## Usage  

```bash
python stock_analysis.py \
    --symbols RELIANCE TCS INFY \
    --output-dir reports \
    [--include-mf] \
    [--no-technical] \
    [--verbose]
```

### Arguments  

| Flag | Description |
|------|-------------|
| `--symbols` | Space‑separated list of ticker symbols (required). |
| `--output-dir` | Directory where JSON and Markdown files will be written (default: `./output`). |
| `--include-mf` | Pull Mutual‑Fund data for the symbols (if applicable). |
| `--no-technical` | Skip local technical‑indicator calculation (useful when AI model already provides them). |
| `--verbose` | Print progress and debugging information. |
| `-h, --help` | Show help message. |

### Example  

```bash
python stock_analysis.py --symbols RELIANCE TCS --output-dir ./reports --verbose
```

The command will:

1. Fetch OHLCV data for **RELIANCE** and **TCS**.  
2. Compute SMA/EMA/RSI/MACD.  
3. Assemble fundamentals (PE, ROE, …).  
4. POST the enriched payload to the AI analysis endpoint.  
5. Write `RELIANCE.json`, `RELIANCE_report.md`, `TCS.json`, and `TCS_report.md` into `./reports`.  

---  

## Output  

- **JSON file** (`{ticker}.json`) – structured data containing:
  ```json
  {
    "ticker": "RELIANCE",
    "ohlcv": [{ "date": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ... }, …],
    "fundamentals": { "pe": ..., "roe": ..., ... },
    "technical": { "sma_20": ..., "rsi": ..., "macd": {...} },
    "ai_analysis": { "summary": "...", "score": 0.92 }
  }
  ```
- **Markdown report** (`{ticker}_report.md`) – human‑readable summary with tables and optional charts (embedded as base64 PNG).  

---  

## Testing  

A minimal test suite lives in the `tests/` folder.

```bash
# Run all tests
pytest
```

Tests mock external API calls, validate data‑transformation logic, and ensure the AI‑wrapper payload is correctly built.  

---  

## Contributing  

Contributions are welcome! Please:

1. Fork the repository.  
2. Create a feature branch (`git checkout -b feat/awesome-feature`).  
3. Write tests for any new functionality.  
4. Ensure `pytest` passes and the code follows PEP‑8.  
5. Open a Pull Request with a clear description of the change.  

---  

*Happy analyzing!*  
