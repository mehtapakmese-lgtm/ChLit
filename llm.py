import os, json, re
import anthropic

MAIN = os.getenv("MAIN_MODEL", "claude-sonnet-5-5")
GATE = os.getenv("GATE_MODEL", "claude-haiku-5-5")
client = anthropic.Anthropic()

SYSTEM = """Sen, çocuk ve gençlik edebiyatı alanında DAAD doktora bursu projesi hazırlayan bir adaya yardım eden akademik asistansın.
KAPSAM: yalnızca çocuk/gençlik edebiyatı (resimli kitap, masal ve fantastik anlatı, çeviri, göç ve çokkültürlülük, okuma kültürü, kuram ve tarih vb.). Kapsam dışı isteklerde nazikçe reddet.
KAYNAK KURALLARI (kesin):
1. Yalnızca sana verilen <references> bloğundaki kaynaklara atıf yap; atıf biçimi [R3] gibi olmalı.
2. Hafızandan yazar, yıl, başlık, DOI, sayfa numarası UYDURMA. Bir iddia için listede kaynak yoksa "[kaynak gerekli]" yaz.
3. Bir kaynağın içeriği hakkında yalnızca verilen özet/künyeye dayanarak konuş; özet yoksa bunu belirt.
4. Kuram ve yazar adlarını genel bilgi olarak anabilirsin ama bunları "[doğrulanmalı]" ile işaretle ve referans listesine koşma.
5. Akademik Türkçe kullan (kullanıcı başka dil isterse onu kullan). Eleştirel ve somut ol."""

def gate(user_text):
    """Alan kapısı: istek çocuk edebiyatı kapsamında mı?"""
    r = client.messages.create(model=GATE, max_tokens=100, messages=[{"role": "user", "content":
        'Aşağıdaki metin çocuk/gençlik edebiyatı akademik araştırmasıyla ilgili mi? '
        'Yalnızca JSON döndür: {"in_scope": true|false}\n\n' + user_text}])
    try:
        return json.loads(re.search(r"\{.*\}", r.content[0].text, re.S).group())["in_scope"]
    except Exception:
        return True

def refs_block(refs):
    lines = []
    for i, r in enumerate(refs, 1):
        lines.append(f"[R{i}] {', '.join(r['authors'][:4])} ({r['year']}). {r['title']}. {r['venue']}. "
                     f"DOI: {r.get('doi')}. Doğrulama: {'EVET' if r['verified'] else 'HAYIR'}\n"
                     f"Özet: {r['abstract'][:900] or '(özet yok)'}")
    return "<references>\n" + "\n\n".join(lines) + "\n</references>"

def generate(stage_prompt, project_ctx, refs, user_notes, extra=""):
    content = (f"<project_so_far>\n{project_ctx}\n</project_so_far>\n\n{refs_block(refs)}\n\n"
               f"{('<external_text>'+extra+'</external_text>') if extra else ''}\n\n"
               f"<user_notes>\n{user_notes}\n</user_notes>\n\nGörev: {stage_prompt}")
    r = client.messages.create(model=MAIN, max_tokens=3500, system=SYSTEM,
                               messages=[{"role": "user", "content": content}])
    text = r.content[0].text
    bad = sorted({c for c in re.findall(r"\[R(\d+)\]", text) if int(c) > len(refs) or int(c) == 0})
    return text, bad

def suggest_queries(topic_notes):
    r = client.messages.create(model=GATE, max_tokens=400, messages=[{"role": "user", "content":
        "Çocuk edebiyatı alanında şu araştırma fikri için akademik veritabanında kullanılacak 4 kısa arama sorgusu "
        "öner (2'si İngilizce, 1'i Almanca, 1'i Türkçe). Her satıra bir sorgu, başka metin yok.\n\n" + topic_notes}])
    return [l.strip("-• ").strip() for l in r.content[0].text.splitlines() if l.strip()]
