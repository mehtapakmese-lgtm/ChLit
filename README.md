# Çocuk Edebiyatı · DAAD Doktora Projesi Asistanı
Kurulum:
    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env    # anahtar ve e-postanızı yazın
    streamlit run app.py

Çalışma mantığı: referanslar OpenAlex'ten gelir, Crossref ile doğrulanır; model yalnızca onayladığınız
kaynaklara [R#] ile atıf yapabilir. Referans listesi APA için koddan üretilir (LLM'den değil).
