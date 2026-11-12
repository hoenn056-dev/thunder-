name: Market Time & Alerts
on:
  schedule:
    # يعمل في الدقيقة 0 من كل ساعة (للفحص)
    - cron: '0 * * * *' 
  workflow_dispatch: # يسمح بالتشغيل اليدوي

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install yfinance pandas_ta_classic requests
      - run: python scanner.py
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
