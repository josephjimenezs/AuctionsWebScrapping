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
    base_remate, base_moneda = None, None
    m = re.search(r"((?:base(?:\s+de)?\s+remate|con una base de)\s*[:\uff1a]?\s*[^\.\n]{1,200})", entry, re.I)
    if m:
        base_remate = m.group(1).strip()
        
        # Determine currency based on the context in base_remate
        if re.search(r"d(?:o|ó)lar(?:es)?|us(?:d)?|\$", base_remate, re.I):
            base_moneda = "DOLARES"
        else:
            base_moneda = "COLONES"
                
    return base_remate, base_moneda

def extraer_base_remate_texto(entry: str) -> str | None:
    """
    Extrae el valor de la base del remate como texto, incluyendo CÉNTIMOS/EXACTOS.
    """
    pattern = r"Con una base de\s+(.*?(?:CÉNTIMOS|EXACTOS),?)"
    match = re.search(pattern, entry, re.IGNORECASE | re.DOTALL)
    if match:
        texto_base = match.group(1).strip()
        texto_base = re.sub(r'\s+', ' ', texto_base)
        return texto_base.replace(",", "")
    return None

def texto_a_moneda(texto: str) -> float | None:
    if not texto or not isinstance(texto, str):
        return None

    texto = normalizar_texto(texto)
    # clean up words that are not numbers
    texto = texto.replace("exactos", "").strip()
    texto = texto.replace("colones", "").strip()
    texto = texto.replace("dolares", "").strip()
    texto = texto.replace("de", "").strip()
    texto = re.sub(r"\s+", " ", texto)

    # Handling "un mil" as "mil"
    if texto == "un mil":
        texto = "mil"

    words = texto.split()
    if not words:
        return None

    # dictionary mapping number words to their values
    word_map = {
        'cero': 0, 'un': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
        'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'dieciseis': 16, 'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19,
        'veinte': 20, 'veintiun': 21, 'veintiuno': 21, 'veintidos': 22, 'veintitres': 23, 'veinticuatro': 24, 'veinticinco': 25, 'veintiseis': 26, 'veintisiete': 27, 'veintiocho': 28, 'veintinueve': 29,
        'treinta': 30, 'cuarenta': 40, 'cincuenta': 50, 'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90,
        'cien': 100, 'ciento': 100, 'doscientos': 200, 'trescientos': 300, 'cuatrocientos': 400, 'quinientos': 500, 'seiscientos': 600, 'setecientos': 700, 'ochocientos': 800, 'novecientos': 900
    }
    
    multipliers = {
        'mil': 1000,
        'millon': 1000000,
        'millones': 1000000
    }

    total = 0
    current_number = 0

    for word in words:
        if word in word_map:
            current_number += word_map[word]
        elif word in multipliers:
            if current_number == 0:
                current_number = 1
            total += current_number * multipliers[word]
            current_number = 0
        else:
            try:
                cleaned_word = re.sub(r'[^0-9]', '', word)
                if cleaned_word:
                    current_number += int(cleaned_word)
            except ValueError:
                pass # ignore words we don't know

    total += current_number
    return float(total) if total > 0 else None

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
            exp = re.search(r"Exp(?:ediente)?[ :.\s]+([0-9A-Za-z\-/\.]+)", entry, re.I)
            juz = re.search(r"(JUZGADO[^\.;]{0,200})", entry, re.I)
            fecha = re.search(r"(\d{1,2}\s+de\s+[A-Za-záéíóúñ]+\s+de\s+\d{4})", entry, re.I)

            provincia = extraer_provincia(entry)

            canton = None
            m = re.search(r"Cant[oó]n[:\uff1a]?\s*((?:[0-9]{1,2}\s*[- ]?\s*)?[A-Za-zÁÉÍÓÚÑ ]+)", entry, re.I)
            if m:
                canton = limpiar_nombre_geo(m.group(1))

            distrito = None
            m = re.search(r"Distrito[:\uff1a]?\s*((?:[0-9]{1,2}\s*[- ]?\s*)?[A-Za-zÁÉÍÓÚÑ ]+)", entry, re.I)
            if m:
                distrito = limpiar_nombre_geo(m.group(1))

            base_remate, base_moneda = extraer_base(entry)
            base_remate_texto = extraer_base_remate_texto(entry)

            records.append({
                "referencia": referencia,
                "expediente": exp.group(1) if exp else None,
                "juzgado": juz.group(1).strip() if juz else None,
                "fecha": fecha.group(1) if fecha else None,
                "provincia": provincia.upper(),
                "canton": canton,
                "distrito": distrito,
                "base_moneda": base_moneda,
                "base_remate_numero": texto_a_moneda(base_remate_texto),
                "base_remate_texto": base_remate_texto,
                "texto_completo": entry[:5000]
            })

    df = pd.DataFrame(records)
    df.to_excel(output_excel, index=False)
    print(f"✅ Guardado {len(df)} remates en {output_excel} (tomando referencia del <p> siguiente)")
    return df

def limpiar_nombre_geo(texto: str) -> str:
    """Quita número inicial y tildes, deja el nombre limpio en mayúsculas."""
    if not texto:
        return None
    # Si viene como "6-GUÁCIMO", "6 GUACIMO", o solo "GUACIMO"
    match = re.match(r"^(?:[0-9]{1,2}\s*[- ]?\s*)?([A-Za-zÁÉÍÓÚÑ ]+)", texto.strip())
    if match:
        nombre = match.group(1)
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
