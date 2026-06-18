import os
import psycopg2
from document_parser import extract_text_from_file, ALL_EXTENSIONS


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="search_agent",
        user="postgres",
        password="123"
    )


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS documents;")

    cursor.execute("""
    CREATE TABLE documents (
        id SERIAL PRIMARY KEY,
        filename TEXT,
        line_no TEXT,
        content TEXT,
        search_vector tsvector
    );
    """)

    cursor.execute("""
    CREATE INDEX idx_documents_search
    ON documents
    USING GIN(search_vector);
    """)

    conn.commit()
    conn.close()


def run_indexer(target_folder):

    print(f"\nIndexing files inside '{target_folder}'...")

    init_database()

    conn = get_connection()
    cursor = conn.cursor()

    for root, dirs, files in os.walk(target_folder):

        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file in files:

            if file.startswith('.'):
                continue

            _, ext = os.path.splitext(file.lower())

            if ext in ALL_EXTENSIONS:

                filepath = os.path.join(root, file)
                filename = os.path.basename(filepath)

                content_lines = extract_text_from_file(filepath)

                if content_lines:

                    batch = [
                        (
                            filename,
                            line_no,
                            line_content,
                            line_content
                        )
                        for line_content, line_no in content_lines
                    ]

                    cursor.executemany(
                        """
                        INSERT INTO documents
                        (
                            filename,
                            line_no,
                            content,
                            search_vector
                        )
                        VALUES
                        (
                            %s,
                            %s,
                            %s,
                            to_tsvector('english', %s)
                        )
                        """,
                        batch
                    )

    conn.commit()
    conn.close()

    print("Indexing complete!")


def search_index(query_str):

    query_str = query_str.strip()

    if not query_str:
        return

    words = query_str.split()

    ts_query = " & ".join(words)

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT
        filename,
        line_no,
        content
    FROM documents
    WHERE
        search_vector @@ to_tsquery('english', %s)
        OR filename ILIKE %s
    LIMIT 20;
    """

    try:

        cursor.execute(
            sql,
            (
                ts_query,
                f"%{query_str}%"
            )
        )

        rows = cursor.fetchall()

        if not rows:

            print("\nNo matching files found.")

        else:

            print(f"\n--- Found {len(rows)} matches ---")

            for idx, row in enumerate(rows, 1):

                filename, line_no, content = row

                print(f"{idx}. File: {filename} ({line_no})")
                print(f"   [Context] {content}")
                print("-" * 60)

    except Exception as e:

        print(f"Search error: {e}")

    finally:

        conn.close()