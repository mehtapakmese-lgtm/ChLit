import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import sources as S, llm as L

st.set_page_config(page_title="Çocuk Edebiyatı · DAAD Proje Asistanı", layout="wide")

STAGES = {
 "1. Konu keşfi": "İlgi alanlarına dayanarak 3-5 olası araştırma sorusu öner; her biri için verilen kaynaklardan hareketle kısa literatür haritası çıkar.",
 "2. Araştırma boşluğu": "Verilen kaynaklara dayanarak alandaki araştırma boşluğunu (gap) belirle. Her boşluk iddiasını [R#] ile temellendir.",
 "3. Araştırma sorusu ve yaklaşım": "Ana araştırma sorusunu, alt soruları ve çalışma varsayımlarını/yaklaşımını keskinleştir.",
 "4. Kuramsal çerçeve": "Uygun kuramsal çerçeveyi öner ve gerekçelendir. Kaynakla desteklenmeyen kuramcıları [doğrulanmalı] diye işaretle.",
 "5. Yöntem": "Korpus oluşturma, çözümleme yöntemi, etik/erişim ve riskleri içeren bir yöntem bölümü taslağı yaz.",
 "6. Almanya bağlantısı": "Verilen kurum/yazar özeti ve (varsa) DAAD metnine dayanarak, neden Almanya'da yapılması gerektiğini ve olası ev sahibi kurum/danışman profillerini gerekçelendir. DAAD koşullarını yalnızca verilen metinden aktar; kesin olmayanları belirt. Ayrıca danışmana ilk e-posta taslağı ekle.",
 "7. Zaman planı": "Burs süresine uygun dönemlere bölünmüş gerçekçi bir çalışma takvimi (tablo) hazırla.",
 "8. Proje metni": "Özet, motivasyon, özgün katkı, Türkiye-Almanya bağlamında değer bölümlerini içeren proje metnini yaz. Sınırlar: kullanıcının notlarındaki kelime/sayfa sınırına uy.",
 "9. Referans listesi": None,
 "10. Eleştirel gözden geçirme": "Projeyi sıkı bir DAAD jürisi gözüyle değerlendir: güçlü yönler, zayıf noktalar, belirsizlikler, tutarsızlıklar; her biri için somut düzeltme önerisi ver.",
}

ss = st.session_state
ss.setdefault("refs", [])        # onaylanan referanslar
ss.setdefault("results", [])     # son arama sonuçları
ss.setdefault("outputs", {})     # aşama çıktıları
ss.setdefault("queries", [])

st.title("📚 Çocuk Edebiyatı · DAAD Doktora Projesi Asistanı")
st.caption("Referanslar yalnızca OpenAlex'ten çekilir ve Crossref ile doğrulanır; model kaynak uyduramaz.")

stage = st.sidebar.radio("Aşama", list(STAGES))
st.sidebar.markdown(f"**Bibliyografya:** {len(ss.refs)} kaynak")
for i, r in enumerate(ss.refs, 1):
    st.sidebar.caption(f"[R{i}] {r['authors'][0] if r['authors'] else '?'} ({r['year']}) {'✅' if r['verified'] else '⚠️'}")
year_from = st.sidebar.number_input("En erken yayın yılı", 1980, 2026, 2005)

def context():
    return "\n\n".join(f"## {k}\n{v}" for k, v in ss.outputs.items())

st.header(stage)
notes = st.text_area("Notlarınız (ilgi alanı, fikirler, kısıtlar, DAAD sınırları...)", height=140, key=f"n_{stage}")

# ---------- Referans tarama ----------
if stage != "9. Referans listesi":
    with st.expander("🔎 Literatür tara ve kaynak ekle", expanded=True):
        c1, c2 = st.columns([4, 1])
        if c2.button("Sorgu öner") and notes:
            if L.gate(notes): ss.queries = L.suggest_queries(notes)
            else: st.warning("Bu istek çocuk edebiyatı kapsamı dışında görünüyor.")
        if ss.queries: st.write("Önerilen sorgular:", " · ".join(f"`{q}`" for q in ss.queries))
        q = c1.text_input("Arama sorgusu", key=f"q_{stage}")
        de = st.checkbox("Yalnızca Almanya kurumlarıyla ilişkili yayınlar", value=stage.startswith("6"))
        if st.button("Tara") and q:
            with st.spinner("OpenAlex taranıyor, Crossref ile doğrulanıyor..."):
                res = S.search_works(q, year_from, 25, de)
                ss.results = [S.verify_crossref(r) for r in res]
        if stage.startswith("6") and ss.results:
            inst, auth = S.institution_summary(ss.results)
            st.write("**Almanya'daki kurumlar (sonuçlara göre):**", inst)
            st.write("**Sık görünen yazarlar:**", auth)
        for i, r in enumerate(ss.results):
            col1, col2 = st.columns([6, 1])
            col1.markdown(f"{'✅' if r['verified'] else '⚠️'} **{r['title']}** — {', '.join(r['authors'][:3])} "
                          f"({r['year']}), *{r['venue']}* · atıf: {r['cited_by']}  \n"
                          f"<small>{r['verify_note']} · DOI: {r.get('doi')}</small>", unsafe_allow_html=True)
            if col2.button("Ekle", key=f"add{i}") and r["openalex_id"] not in {x["openalex_id"] for x in ss.refs}:
                ss.refs.append(r); st.rerun()

# ---------- DAAD sayfası ----------
extra = ""
if stage.startswith("6"):
    url = st.text_input("Güncel DAAD çağrı/program sayfasının URL'si (koşulları buradan çekeriz)")
    if url and st.button("Sayfayı çek"):
        ss["daad_text"] = S.fetch_page_text(url)
    extra = ss.get("daad_text", "")
    if extra: st.success(f"{len(extra)} karakter çekildi.")

# ---------- Üretim ----------
if stage == "9. Referans listesi":
    st.subheader("APA 7 (Crossref verisinden deterministik üretim)")
    ok = [r for r in ss.refs if r["verified"]]
    for r in sorted(ok, key=lambda x: (x["authors"][0] if x["authors"] else "")):
        st.write(S.apa(r))
    un = [r for r in ss.refs if not r["verified"]]
    if un:
        st.warning("Doğrulanmamış kaynaklar – kullanmadan önce elle kontrol edin:")
        for r in un: st.write("• " + S.apa(r))
else:
    if st.button("Aşama taslağını üret", type="primary"):
        if not L.gate(notes + " " + stage):
            st.warning("Bu istek çocuk edebiyatı kapsamı dışında; yardımcı olamam.")
        else:
            with st.spinner("Yazılıyor..."):
                text, bad = L.generate(STAGES[stage], context(), ss.refs, notes, extra)
            ss.outputs[stage] = text
            if bad: st.error(f"Listede olmayan atıflar bulundu: {bad} — bunlara güvenmeyin.")
    if stage in ss.outputs:
        ss.outputs[stage] = st.text_area("Taslak (düzenleyebilirsiniz)", ss.outputs[stage], height=400)

if ss.outputs:
    st.sidebar.download_button("Tüm taslağı indir (.md)", context(), "daad_proje_taslagi.md")
