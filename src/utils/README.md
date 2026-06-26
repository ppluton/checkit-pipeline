# Utils

Briques transverses partagées par les couches extraction, transformation
et monitoring.

## Modules

### `config.py`

Point d'entrée unique de la configuration.

- Charge `.env` une seule fois à l'import (`python-dotenv`).
- Expose les secrets (`GUARDIAN_API_KEY`, `FAKEDDIT_TSV_PATH`) et les
  chemins (`RAW_DIR`, `PROCESSED_DIR`, `PROJECT_ROOT`).
- Aucun `os.getenv` dans le code métier : config centralisée,
  monkeypatchable en test.

### `logger.py`

Factory de logger standardisé (`get_logger(__name__)`).

- Format uniforme, sortie stdout (capturée par Airflow).
- Idempotent (`if logger.handlers: return`) : pas de lignes dupliquées.
- `propagate=False` : évite le double-print via le root logger d'Airflow.

### `io.py`

Helpers de lecture/écriture JSON Lines, factorisés depuis les extracteurs.

- `write_jsonl(records, source, ...)` : écrit dans
  `data/raw/<source>/`. Accepte un itérable (streaming, jamais tout en
  mémoire) ; nom horodaté par défaut pour ne pas écraser les runs.
- `write_processed(lines, ...)` : écrit dans `data/processed/`.
- `read_jsonl(path)` : charge un JSONL en liste de dicts.
- `latest_raw_file(source)` : dernier `*.jsonl` écrit pour une source
  (par date de modification).
