import csv
import sqlite3


def import_lista_migrate(csv_filename="listaMigrate.csv"):
    conn = sqlite3.connect("dictionary.db")
    cursor = conn.cursor()

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
            # Obtener los valores sin importar minúsculas/mayúsculas en las llaves
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

            # Omitir filas sin palabra en inglés
            if not english:
                continue

            # Verificar si ya existe en la base de datos
            cursor.execute(
                "SELECT id FROM vocabulary WHERE lower(english)=lower(?)",
                (english,),
            )
            existing = cursor.fetchone()

            if not existing:
                cursor.execute(
                    """
                    INSERT INTO vocabulary
                    (english, spanish, type, level, pronunciation, example_en, example_es, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                print(f"➕ Importada: {english}")
            else:
                rows_skipped += 1
                print(f"⚠️ Omitida (ya existe): {english}")

    conn.commit()
    conn.close()

    print("\n----------------------------------------")
    print(
        f"✅ Resumen: {rows_inserted} agregadas | {rows_skipped} ya existían."
    )


if __name__ == "__main__":
    import_lista_migrate()