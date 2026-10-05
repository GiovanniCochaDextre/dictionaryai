import csv
import os
from dotenv import load_dotenv
import psycopg2

# Cargar variables del archivo .env si existe
load_dotenv()


def import_lista_migrate(csv_filename="listaMigrate.csv"):
    # Obtener la URL de conexión de Supabase desde el archivo .env
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        db_url = input(
            "Pega la URI de Supabase (DATABASE_URL) con tu contraseña: "
        ).strip()

    print("🔌 Conectando a Supabase PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Asegurar que la tabla 'vocabulary' exista antes de insertar
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id SERIAL PRIMARY KEY,
            english TEXT UNIQUE NOT NULL,
            spanish TEXT,
            type TEXT,
            level TEXT,
            pronunciation TEXT,
            example_en TEXT,
            example_es TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    conn.commit()

    rows_inserted = 0
    rows_skipped = 0

    # utf-8-sig resuelve problemas con archivos CSV exportados desde Excel (BOM)
    with open(csv_filename, mode="r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        # Normalizar los nombres de las columnas (eliminar espacios accidentales)
        reader.fieldnames = [
            header.strip() if header else header for header in reader.fieldnames
        ]

        for row in reader:
            english = (
                row.get("English") or row.get("english") or ""
            ).strip()
            spanish = (
                row.get("Spanish") or row.get("spanish") or ""
            ).strip()
            word_type = (row.get("Type") or row.get("type") or "").strip()
            example_en = (
                row.get("Example (EN)") or row.get("example_en") or ""
            ).strip()
            example_es = (
                row.get("Example (ES)") or row.get("example_es") or ""
            ).strip()
            notes = (row.get("Notes") or row.get("notes") or "").strip()

            if not english:
                continue

            # En PostgreSQL se usa %s en lugar de ?
            cursor.execute(
                "SELECT id FROM vocabulary WHERE lower(english) = lower(%s)",
                (english,),
            )
            existing = cursor.fetchone()

            if not existing:
                cursor.execute(
                    """
                    INSERT INTO vocabulary
                    (english, spanish, type, level, pronunciation, example_en, example_es, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        english,
                        spanish,
                        word_type,
                        "",
                        "",
                        example_en,
                        example_es,
                        notes,
                    ),
                )
                rows_inserted += 1
                print(f"➕ Importada a Supabase: {english}")
            else:
                rows_skipped += 1
                print(f"⚠️ Omitida (ya existe): {english}")

    conn.commit()
    cursor.close()
    conn.close()

    print("\n----------------------------------------")
    print(
        f"✅ Migración completada: {rows_inserted} agregadas | {rows_skipped} ya existían."
    )


if __name__ == "__main__":
    import_lista_migrate()