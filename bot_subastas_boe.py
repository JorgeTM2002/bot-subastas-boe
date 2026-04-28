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
    "campo[9]": "SUBASTA.POSTURA_MINIMA_MINIMA_LOTES", "dato[9]": "35000000",
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
        json.dumps(sorted(list(vistas)), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def notificar(mensaje):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"

    r = requests.post(
        url,
        data=mensaje.encode("utf-8"),
        headers={
            "Title": "Nueva subasta vivienda Madrid",
            "Priority": "high",
            "Tags": "house,warning"
        },
        timeout=20
    )

    print("Enviando a:", url)
    print("NTFY status:", r.status_code)
    print("NTFY response:", r.text)

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


def main():
    # Prueba para confirmar que GitHub Actions envía al móvil
    notificar("Prueba desde GitHub Actions: bot BOE funcionando")

    vistas = cargar_vistas()
    subastas = buscar_subastas()

    nuevas = 0

    for id_subasta, link in subastas.items():
        if id_subasta not in vistas:
            mensaje = (
                f"Nueva subasta de vivienda en Madrid\n\n"
                f"{id_subasta}\n"
                f"Postura mínima inferior a 350.000 €\n\n"
                f"{link}"
            )

            notificar(mensaje)
            vistas.add(id_subasta)
            nuevas += 1

    guardar_vistas(vistas)

    print(f"Subastas encontradas: {len(subastas)}")
    print(f"Nuevas notificadas: {nuevas}")


if __name__ == "__main__":
    main()
