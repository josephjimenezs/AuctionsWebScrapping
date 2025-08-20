import sys
import re
import unicodedata
import pandas as pd
from bs4 import BeautifulSoup

PROVINCIAS_VALIDAS = [
    "puntarenas", "alajuela", "guanacaste",
    "san jose", "heredia", "limon", "cartago"
]

def normalizar_texto(texto: str) -> str:
    txt = unicodedata.normalize("NFKD", texto)
    txt = "".join(c for c in txt if not unicodedata.combining(c)).lower()
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()

def contiene_remate_finca(texto: str) -> bool:
    return "remate la finca" in normalizar_texto(texto)

def extraer_provincia(entry: str) -> str | None:
    ntxt = normalizar_texto(entry)
    for prov in PROVINCIAS_VALIDAS:
        if re.search(rf"\b{re.escape(prov)}\b", ntxt, re.I):
            return prov.title()
    return None

def extraer_base(entry: str):
    base_remate, base_valor, base_moneda = None, None, None
    m = re.search(r"(base(?:\s+de)?\s+remate\s*[:\uFF1A]?\s*[^\.\n]{1,200})", entry, re.I)
    if m:
        base_remate = m.group(1).strip()
        m2 = re.search(r"(₡|¢|US\$|\$|USD)\s?([0-9\.,]+)", base_remate)
        if m2:
            raw = m2.group(0)
            if "₡" in raw or "¢" in raw or re.search(r"colones", raw, re.I):
                base_moneda = "COLONES"
            else:
                base_moneda = "DOLARES"
            num = re.sub(r"[^0-9,\.]", "", raw)
            num = num.replace(".", "").replace(",", ".")
            try:
                base_valor = float(num)
            except:
                base_valor = None
    return base_remate, base_valor, base_moneda

def parse_html_remates(path_html, output_excel="remates_html.xlsx"):
    with open(path_html, "rb") as f:
        soup = BeautifulSoup(f, "lxml")

    ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]

    records = []
    for i, text in enumerate(ps):
        if contiene_remate_finca(text):
            # Texto del remate
            entry = text

            # Buscar referencia en el <p> siguiente
            referencia = None
            if i + 1 < len(ps):
                siguiente = ps[i + 1]
                m = re.search(r"Referencia\s*N[°º]?\s*[:\-]?\s*([A-Za-z0-9./\-]+)", siguiente, re.I)
                if m:
                    referencia = m.group(1).strip()

            # Campos básicos
            exp = re.search(r"Exp(?:ediente)?[:\.\s]+([0-9A-Za-z\-/\.]+)", entry, re.I)
            juz = re.search(r"(JUZGADO[^\.;]{0,200})", entry, re.I)
            fecha = re.search(r"(\d{1,2}\s+de\s+[A-Za-záéíóúñ]+\s+de\s+\d{4})", entry, re.I)

            provincia = extraer_provincia(entry)



#            canton = None
#            m = re.search(r"Cant[oó]n[:\uFF1A]?\s*([A-Za-zÁÉÍÓÚÑ0-9 ]{2,60})", entry, re.I)
#            if m: canton = m.group(1).strip()

#            distrito = None
#            m = re.search(r"Distrito[:\uFF1A]?\s*([A-Za-zÁÉÍÓÚÑ0-9 ]{2,60})", entry, re.I)
#            if m: distrito = m.group(1).strip()

            canton = None
            m = re.search(r"Cant[oó]n[:\uFF1A]?\s*([0-9]{1,2}\s*-\s*[A-Za-zÁÉÍÓÚÑ ]+)", entry, re.I)
            if m:
                canton = limpiar_nombre_geo(m.group(1))

            distrito = None
            m = re.search(r"Distrito[:\uFF1A]?\s*([0-9]{1,2}\s*-\s*[A-Za-zÁÉÍÓÚÑ ]+)", entry, re.I)
            if m:
                distrito = limpiar_nombre_geo(m.group(1))




            base_remate, base_valor, base_moneda = extraer_base(entry)

            records.append({
                "referencia": referencia,
                "expediente": exp.group(1) if exp else None,
                "juzgado": juz.group(1).strip() if juz else None,
                "fecha": fecha.group(1) if fecha else None,
                "provincia": provincia,
                "canton": canton,
                "distrito": distrito,
                "base_remate": base_remate,
                "base_valor": base_valor,
                "base_moneda": base_moneda,
                "texto_completo": entry[:1000]
            })

    df = pd.DataFrame(records)
    df.to_excel(output_excel, index=False)
    print(f"✅ Guardado {len(df)} remates en {output_excel} (tomando referencia del <p> siguiente)")
    return df

def limpiar_nombre_geo(texto: str) -> str:
    """Quita número inicial y tildes, deja el nombre limpio en mayúsculas."""
    if not texto:
        return None
    # Si viene como "6-GUÁCIMO"
    if "-" in texto:
        nombre = texto.split("-", 1)[1]
    else:
        nombre = texto
    # Normalizar tildes y mayúsculas
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    return nombre.strip().upper()


# ---------------- CLI ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extraer_remates_html.py <archivo.html> [salida.xlsx]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "remates_html.xlsx"
    parse_html_remates(input_file, output_file)
