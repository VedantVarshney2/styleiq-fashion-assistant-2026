# StyleIQ — Professional Fashion Dataset Assistant

## What's included
- `app.py` — Streamlit multi-page chatbot application
- `fashion_dataset_1000.csv` — your fashion dataset
- `requirements.txt` — Python dependencies

## Features
1. Chat assistant for natural-language catalogue queries
2. Product explorer with combined filters
3. Recommendation page using budget, category, gender and rating
4. Interactive analytics dashboard
5. CSV export for filtered products and recommendations
6. Dataset overview and download

## Run on Windows / VS Code
1. Extract the ZIP.
2. Open the `fashion_assistant_pro` folder in VS Code.
3. Open Terminal > New Terminal.
4. Install packages:
   `python -m pip install -r requirements.txt`
5. Start:
   `python -m streamlit run app.py`
6. Open the local URL shown in the terminal, normally `http://localhost:8501`.

## Important
The included dataset is synthetic demo data, not live retailer inventory. Chat query understanding is rule-based and does not need an API key.
