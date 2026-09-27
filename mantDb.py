import json
import sqlite3
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Inicialización del cliente de Gemini
client = genai.Client()

DB_NAME = "dictionary.db"


def fetch_missing_info_from_gemini(word: str) -> dict:
    """Consulta a Gemini para obtener el nivel (CEFR) y la pronunciación de una palabra."""
    prompt = (
        f"Proporciona únicamente el nivel de inglés (ej. A1, A2, B1, B2, C1, C2) "
        f"y la pronunciación figurada/IPA para la palabra: '{word}'"
    )

    json_schema = {
        "type": "OBJECT",
        "properties": {
            "level": {"type": "STRING"},
            "pronunciation": {"type": "STRING"},
        },
        "required": ["level", "pronunciation"],
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Uso de client.models.generate_content con el SDK google-genai
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": json_schema,
                },
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"  [!] Error al consultar Gemini (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    return {"level": "", "pronunciation": ""}


def update_vocabulary():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Obtener id, english, level y pronunciation de toda la tabla
    cursor.execute(
        "SELECT id, english, level, pronunciation FROM vocabulary ORDER BY id ASC"
    )
    records = cursor.fetchall()

    print(f"Se encontraron {len(records)} registros para procesar.\n")

    for record_id, english, level, pronunciation in records:
        if not english:
            continue

        # 1. Asegurar que la primera letra del inglés sea Mayúscula
        formatted_english = english.strip().capitalize()

        # 2. Verificar si faltan datos en level o pronunciation
        needs_level = not level or not str(level).strip()
        needs_pronunciation = not pronunciation or not str(pronunciation).strip()

        updated_level = level.strip() if level else ""
        updated_pronunciation = pronunciation.strip() if pronunciation else ""

        if needs_level or needs_pronunciation:
            print(
                f"[ID {record_id}] Consultando Gemini para la palabra: '{formatted_english}'..."
            )
            ai_data = fetch_missing_info_from_gemini(formatted_english)

            if needs_level and ai_data.get("level"):
                updated_level = ai_data["level"]

            if needs_pronunciation and ai_data.get("pronunciation"):
                updated_pronunciation = ai_data["pronunciation"]

            # Pausa breve para no saturar el límite de peticiones por minuto (RPM)
            time.sleep(1)

        # 3. Actualizar el registro en la base de datos
        cursor.execute(
            """
            UPDATE vocabulary
            SET english = ?,
                level = ?,
                pronunciation = ?
            WHERE id = ?
            """,
            (formatted_english, updated_level, updated_pronunciation, record_id),
        )

        print(
            f"✔ ID {record_id} actualizado: English='{formatted_english}', "
            f"Level='{updated_level}', Pronunciation='{updated_pronunciation}'"
        )

    conn.commit()
    conn.close()
    print("\n¡Proceso de actualización finalizado con éxito!")


if __name__ == "__main__":
    update_vocabulary()