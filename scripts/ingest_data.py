import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.rag.vector_store import VectorStore


def _load_json_documents(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    source = path.stem
    documents: list[dict[str, object]] = []
    for item in data:
        if isinstance(item, dict):
            text = item.get("content") or item.get("text") or json.dumps(item, ensure_ascii=True)
            documents.append(
                {
                    "text": text,
                    "source": source,
                    "title": item.get("topic") or item.get("title") or source,
                    "metadata": item,
                }
            )
        else:
            documents.append({"text": str(item), "source": source, "title": source, "metadata": {}})
    return documents


def main() -> None:
    docs: list[dict[str, object]] = []
    docs.extend(_load_json_documents(ROOT_DIR / "data" / "invoices.json"))
    docs.extend(_load_json_documents(ROOT_DIR / "data" / "transactions.json"))
    docs.extend(_load_json_documents(ROOT_DIR / "data" / "reminders.json"))
    docs.extend(_load_json_documents(ROOT_DIR / "data" / "knowledge_base.json"))

    if not docs:
        print("No documents found to ingest.")
        return

    vector_store = VectorStore()
    vector_store.add_documents(docs)
    vector_store.save()
    print(f"Ingested {len(docs)} documents.")


if __name__ == "__main__":
    main()
