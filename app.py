import json
import os
import sqlite3
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request
from google import genai
from google.genai import types

# Cargar variables de entorno desde .env
load_dotenv()

app = Flask(__name__)

# Definir la ruta absoluta de la base de datos para asegurar persistencia en la nube
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dictionary.db")

# Detectar URL de base de datos PostgreSQL en Render/Supabase/Neon
DATABASE_URL = os.environ.get("DATABASE_URL")

# Configuración del cliente Gemini
# Lee automáticamente la variable de entorno GEMINI_API_KEY
client = genai.Client()


def get_db_connection():
    """Crea y retorna una conexión a SQLite o PostgreSQL según el entorno."""
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras

        # Asegurar prefijo postgresql:// exigido por drivers actuales
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        conn = psycopg2.connect(db_url)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Crea la tabla si no existe al iniciar la aplicación."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # Sintaxis para PostgreSQL
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id SERIAL PRIMARY KEY,
            english TEXT,
            spanish TEXT,
            type TEXT,
            level TEXT,
            pronunciation TEXT,
            example_en TEXT,
            example_es TEXT,
            notes TEXT
        )
        """
        )
    else:
        # Sintaxis para SQLite
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english TEXT,
            spanish TEXT,
            type TEXT,
            level TEXT,
            pronunciation TEXT,
            example_en TEXT,
            example_es TEXT,
            notes TEXT
        )
        """
        )

    conn.commit()
    conn.close()


# Inicializar la base de datos
init_db()


@app.route("/generate")
def generate():
    word = request.args.get("word", "").strip()

    if not word:
        return jsonify({"error": "No word provided"}), 400

    # Prompt explícito: Especifica que el objetivo de aprendizaje es el INGLÉS.
    prompt = (
        f"El usuario desea aprender inglés y ha proporcionado el término: '{word}'. "
        f"Si la palabra está en español, tradúcela primero al inglés. "
        f"Genera los datos para el diccionario asegurando que el campo 'pronunciation' "
        f"corresponda SIEMPRE a la pronunciación (fonética o figurada) de la palabra EN INGLÉS."
    )

    # Schema JSON estructurado refinado
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "english": {
                "type": "STRING",
                "description": "La palabra o frase en inglés.",
            },
            "spanish": {
                "type": "STRING",
                "description": "Traducción al español.",
            },
            "type": {
                "type": "STRING",
                "description": "Categoría gramatical (Noun, Verb, Adjective, Phrasal Verb, etc.).",
            },
            "level": {
                "type": "STRING",
                "description": "Nivel CEFR (A1, A2, B1, B2, C1, C2).",
            },
            "pronunciation": {
                "type": "STRING",
                "description": "Pronunciación en inglés (ej. IPA o figurada en español como 'ápl'). NUNCA la pronunciación en español.",
            },
            "example_en": {
                "type": "STRING",
                "description": "Ejemplo de uso en inglés.",
            },
            "example_es": {
                "type": "STRING",
                "description": "Traducción del ejemplo al español.",
            },
            "notes": {
                "type": "STRING",
                "description": "Notas gramaticales, sinónimos o consejos de uso.",
            },
        },
        "required": [
            "english",
            "spanish",
            "type",
            "level",
            "pronunciation",
            "example_en",
            "example_es",
            "notes",
        ],
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            interaction = client.interactions.create(
                model="gemini-3.8-flash",
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": json_schema,
                },
            )

            data = json.loads(interaction.output_text)
            return jsonify(data)

        except Exception as e:
            print(f"Intento {attempt + 1} fallido: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return (
                    jsonify(
                        {
                            "error": "Error de comunicación con el servicio de IA"
                        }
                    ),
                    500,
                )


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        english = request.form.get("english", "").strip()
        spanish = request.form.get("spanish", "").strip()
        word_type = request.form.get("type", "").strip()
        level = request.form.get("level", "").strip()
        pronunciation = request.form.get("pronunciation", "").strip()
        example_en = request.form.get("example_en", "").strip()
        example_es = request.form.get("example_es", "").strip()
        notes = request.form.get("notes", "").strip()

        if english:
            english_formatted = english.capitalize()

            conn = get_db_connection()
            cursor = conn.cursor()

            # Marcador de posición adaptativo (? para SQLite, %s para PostgreSQL)
            param = "%s" if DATABASE_URL else "?"

            cursor.execute(
                f"SELECT id FROM vocabulary WHERE lower(english)=lower({param})",
                (english_formatted,),
            )
            existing = cursor.fetchone()

            if not existing:
                query = f"""
                    INSERT INTO vocabulary
                    (english, spanish, type, level, pronunciation, example_en, example_es, notes)
                    VALUES ({param}, {param}, {param}, {param}, {param}, {param}, {param}, {param})
                """
                cursor.execute(
                    query,
                    (
                        english_formatted,
                        spanish,
                        word_type,
                        level,
                        pronunciation,
                        example_en,
                        example_es,
                        notes,
                    ),
                )
                conn.commit()

            conn.close()

        # Evita re-envíos duplicados de formulario al presionar F5
        return redirect("/")

    # Método GET: Obtener todos los registros
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT
        english,
        spanish,
        type,
        level,
        pronunciation,
        example_en,
        example_es,
        notes
    FROM vocabulary
    ORDER BY english ASC
    """
    )

    words = cursor.fetchall()
    conn.close()

    return render_template("index.html", words=words)


if __name__ == "__main__":
    # Lee el puerto que asigna el proveedor de la nube (o 5000 por defecto en local)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)