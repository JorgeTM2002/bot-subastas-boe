import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json
import re
from urllib.parse import urljoin

URL = "https://subastas.boe.es/subastas_ava.php"
BASE = "https://subastas.boe.es/"

NTFY_TOPIC = "subastas-madrid-vivienda-jorge-350k"
SEEN_FILE = Path("subastas_vistas.json")

PRECIO_MAXIMO = 350000

PALABRAS_RIESGO = [
    "ocupada",
    "ocupado",
    "ocupantes",
    "nuda propiedad",
    "usufructo",
    "cuota indivisa",
    "parte indivisa",
    "proindiviso",
    "mitad indivisa",
    "sin posesión",
    "no visitable",
    "arrendada",
    "arrendado",
    "inquilino",
    "lanzamiento",
]

DATA = {
    "campo[0]": "SUBASTA.ORIGEN", "dato[0]": "",
    "campo[1]": "SUBASTA.AUTORIDAD", "dato[1]": "",
    "campo[2]": "SUBASTA.ESTADO.CODIGO", "dato[2]": "PU",
    "campo[3]": "BIEN.TIPO", "dato[3]": "I",
    "campo[4]": "BIEN.SUBTIPO", "dato[4]": "501",
    "campo[5]": "BIEN.DIRECCION", "dato[5]": "",
    "campo[6]": "BIEN.CODPOSTAL", "dato[6]": "",
    "campo[7]": "BIEN.LOCALIDAD", "dato[7]": "Madrid",
    "campo[8]": "BIEN.COD_PROVINCIA", "dato[8]": "28",
    "campo[9]": "SUBASTA.POSTURA_MINIMA_MINIMA_LOTES",
    "dato[9]": str(PRECIO_MAXIMO * 100),
    "campo[10]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_1", "dato[10]": "",
    "campo[11]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_2", "dato[11]": "",
    "campo[12]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_3", "dato[12]": "",
    "campo[13]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_4", "dato[13]": "",
    "campo[14]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_5", "dato[14]": "",
    "campo[15]": "SUBASTA.ID_SUBASTA_BUSCAR", "dato[15]": "",
    "campo[16]": "SUBASTA.ACREEDORES", "dato[16]": "",
    "campo[17]": "SUBASTA.FECHA_FIN", "dato[17][0]": "", "dato[17][1]": "",
    "campo[18]": "SUBASTA.FECHA_INICIO", "dato[18][0]": "", "dato[18][1]": "",
    "page_hits": "50",
    "sort_field[0]": "SUBASTA.FECHA_FIN",
    "sort_order[0]": "asc",
    "accion": "Buscar",
}


def cargar_vistas():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def guardar_vistas(vistas):
    SEEN_FILE.write_text(
        json.dumps(sorted(vistas), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def notificar(mensaje):
    r = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=mensaje.encode("utf-8"),
        headers={
            "Title": "Nueva oportunidad BOE Madrid",
            "Priority": "high",
            "Tags": "house,rotating_light"
        },
        timeout=20
    )
    print("NTFY status:", r.status_code)


def buscar_subastas():
    r = requests.post(URL, data=DATA, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    subastas = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "detalleSubasta.php?idSub=" not in href:
            continue

        match = re.search(r"idSub=([^&]+)", href)
        if not match:
            continue

        id_subasta = match.group(1)
        link = urljoin(BASE, href)
        subastas[id_subasta] = link

    return subastas


def analizar_detalle(link):
    r = requests.get(link, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    texto = soup.get_text(" ", strip=True)
    texto_lower = texto.lower()

    riesgos = [p for p in PALABRAS_RIESGO if p in texto_lower]

    direccion = extraer_fragmento(texto, "Dirección")
    valor_subasta = extraer_fragmento(texto, "Valor subasta")
    tasacion = extraer_fragmento(texto, "Tasación")

    es_interesante = len(riesgos) == 0

    return {
        "texto": texto,
        "riesgos": riesgos,
        "direccion": direccion,
        "valor_subasta": valor_subasta,
        "tasacion": tasacion,
        "es_interesante": es_interesante,
    }


def extraer_fragmento(texto, palabra, longitud=180):
    pos = texto.lower().find(palabra.lower())
    if pos == -1:
        return ""
    return texto[pos:pos + longitud]


def main():
    vistas = cargar_vistas()
    subastas = buscar_subastas()

    nuevas = 0
    descartadas = 0

    for id_subasta, link in subastas.items():
        if id_subasta in vistas:
            continue

        try:
            detalle = analizar_detalle(link)
        except Exception as e:
            print(f"Error analizando {id_subasta}: {e}")
            continue

        vistas.add(id_subasta)

        if not detalle["es_interesante"]:
            descartadas += 1
            print(f"Descartada {id_subasta}. Riesgos: {detalle['riesgos']}")
            continue

        mensaje = (
            f"Posible oportunidad BOE Madrid\n\n"
            f"{id_subasta}\n"
            f"Filtro: vivienda Madrid < {PRECIO_MAXIMO:,.0f} €\n\n"
            f"{detalle['direccion']}\n\n"
            f"{detalle['valor_subasta']}\n"
            f"{detalle['tasacion']}\n\n"
            f"{link}"
        )

        notificar(mensaje)
        nuevas += 1

    guardar_vistas(vistas)

    print(f"Subastas encontradas: {len(subastas)}")
    print(f"Nuevas notificadas: {nuevas}")
    print(f"Descartadas por riesgo: {descartadas}")


if __name__ == "__main__":
    main()
