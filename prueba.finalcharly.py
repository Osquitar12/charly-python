import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import re
import time

# =========================
# CONFIGURACIÓN GOOGLE SHEETS
# =========================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

CRED_FILE = "creds.json"

CREDS = ServiceAccountCredentials.from_json_keyfile_name(CRED_FILE, SCOPE)

CLIENT = gspread.authorize(CREDS)

SHEET_ID = "1hNM1hd15iGkbjlj4VKV7GcpHB5nL6F45SVawLWUuMRU"

SHEET = CLIENT.open_by_key(SHEET_ID).worksheet("BASE VS2")

# =========================
# UTILIDADES
# =========================
HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_RETRIES = 3

TIMEOUT = 30


def limpiar_precio(texto):

    if not texto:
        return None

    return int(re.sub(r"[^\d]", "", texto))


def fetch_html(url):

    for intento in range(MAX_RETRIES):

        try:

            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            r.raise_for_status()

            return r.text

        except Exception as e:

            print(f"❌ Error HTML {url} ({intento+1}/{MAX_RETRIES}): {e}")

            time.sleep(3)

    return None


def intentar_scraper(func, url):

    for intento in range(MAX_RETRIES):

        try:

            resultado = func(url)

            if resultado:
                return resultado

            print(f"⚠️ Reintentando scraper {url} ({intento+1}/{MAX_RETRIES})")

            time.sleep(2)

        except Exception as e:

            print(f"❌ Error scraper {url} ({intento+1}/{MAX_RETRIES}): {e}")

            time.sleep(3)

    return None


# =========================
# SCRAPERS
# =========================
def extraer_precios_bellapiel(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    tag_actual = soup.select_one(".vtex-product-price-1-x-sellingPriceValue")

    tag_tachado = soup.select_one(".vtex-product-price-1-x-listPriceValue.strike")

    actual = limpiar_precio(tag_actual.text) if tag_actual else None

    tachado = limpiar_precio(tag_tachado.text) if tag_tachado else None

    return actual, tachado


def extraer_precio_dermatologica(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    tag_precio = soup.select_one(".dermatologicaco-components-0-x-price")

    return limpiar_precio(tag_precio.text) if tag_precio else None


def obtener_precios_falabella(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    precios = {"normal": None, "cmr": None}

    li_internet = soup.find("li", attrs={"data-internet-price": True})

    if li_internet:

        precios["normal"] = int(
            li_internet["data-internet-price"].replace(".", "").replace(",", "")
        )

    li_cmr = soup.find("li", attrs={"data-cmr-price": True})

    if li_cmr:

        precios["cmr"] = int(
            li_cmr["data-cmr-price"].replace(".", "").replace(",", "")
        )

    return precios


def extraer_precios_farmatodo(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    actual_tag = soup.select_one(".box__price--current")

    before_tag = soup.select_one(".box__price--before")

    actual = limpiar_precio(actual_tag.text) if actual_tag else None

    before = limpiar_precio(before_tag.text) if before_tag else None

    return actual, before


def extraer_precios_linea_estetica(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    actual_tag = soup.select_one("p.price ins .amount") or soup.select_one(
        "p.price .amount"
    )

    before_tag = soup.select_one("p.price del .amount")

    actual = limpiar_precio(actual_tag.text) if actual_tag else None

    before = limpiar_precio(before_tag.text) if before_tag else None

    return actual, before


def extraer_precios_medipiel(url):

    html = fetch_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    promo_tag = soup.select_one(
        ".medipielsa-components-0-x-price-discount-promo-pdp"
    )

    normal_tag = soup.select_one(".vtex-store-components-3-x-listPriceValue")

    selling_tag = soup.select_one(
        ".vtex-store-components-3-x-sellingPriceValue"
    )

    precio_actual = limpiar_precio(promo_tag.text) if promo_tag else (
        limpiar_precio(selling_tag.text) if selling_tag else None
    )

    precio_normal = limpiar_precio(normal_tag.text) if normal_tag else None

    return precio_actual, precio_normal


# =========================
# ACTUALIZACIÓN DE PRECIOS
# =========================
def actualizar_precios():

    data = SHEET.get_all_values()

    for i, row in enumerate(data[1:], start=2):

        fila_valores = [None] * 25

        # LINEA ESTETICA
        url = row[1] if len(row) > 1 else None

        if url:

            r = intentar_scraper(extraer_precios_linea_estetica, url)

            if r:

                fila_valores[8] = r[0]

                fila_valores[9] = r[1]

        # MEDIPIEL
        url = row[2] if len(row) > 2 else None

        if url:

            r = intentar_scraper(extraer_precios_medipiel, url)

            if r:

                fila_valores[11] = r[0]

                fila_valores[12] = r[1]

        # FALABELLA
        url = row[3] if len(row) > 3 else None

        if url:

            r = intentar_scraper(obtener_precios_falabella, url)

            if r:

                fila_valores[14] = r["normal"]

                fila_valores[15] = r["cmr"]

        # DERMATOLOGICA
        url = row[4] if len(row) > 4 else None

        if url:

            r = intentar_scraper(extraer_precio_dermatologica, url)

            if r:

                fila_valores[17] = r

        # FARMATODO
        url = row[5] if len(row) > 5 else None

        if url:

            r = intentar_scraper(extraer_precios_farmatodo, url)

            if r:

                fila_valores[20] = r[0]

                fila_valores[21] = r[1]

        # BELLA PIEL
        url = row[6] if len(row) > 6 else None

        if url:

            r = intentar_scraper(extraer_precios_bellapiel, url)

            if r:

                fila_valores[23] = r[0]

                fila_valores[24] = r[1]

        for intento in range(MAX_RETRIES):

            try:

                SHEET.update(f"A{i}:Y{i}", [fila_valores])

                print(f"Fila {i} actualizada ✅")

                break

            except Exception as e:

                print(f"❌ Error update fila {i} ({intento+1}/{MAX_RETRIES}): {e}")

                time.sleep(5)

        time.sleep(1)

    print("✅ Actualización completada.")


if __name__ == "__main__":

    actualizar_precios()