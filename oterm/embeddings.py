import asyncio
import argparse
from pathlib import Path
from typing import Iterable, Tuple, Sequence

import aiosql
import aiosqlite
from sentence_transformers import SentenceTransformer
from semantic_text_splitter import TextSplitter
import numpy as np
from sklearn.metrics import euclidean_distances
from tqdm import tqdm
from inscriptis import get_text


def main():
    asyncio.run(async_main())


async def async_main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directory",
        help="Directory in which to initialize the store.",
        type=Path,
        default=Path(".").resolve(),
    )
    args = parser.parse_args()

    root = Path(args.directory)
    store = VectorStore()
    await store.create(root)


async def get_output():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directory",
        help="Directory in which to initialize the store.",
        type=Path,
        default=Path(".").resolve(),
    )
    args = parser.parse_args()

    root = Path(args.directory)
    store = VectorStore()
    await store.load(root)

    message, chat_message = await format_output((store,), "What is a Dataframe")
    print(chat_message)
    print(message)


CONTEXT_DIRECTORY = ".rtfm"
DB_NAME = "embeddings.db"
VECTOR_NAME = "vectors.npy"


async def format_output(stores: Iterable["VectorStore"], message: str, n_documents: int = 3) -> tuple[str, str]:
    retrieved = sorted(
        [
            (distance, source, context)
            for store in stores
            async for (distance, source, context) in store.get_nearest(message, n_nearest=n_documents)
        ]
    )
    chosen = retrieved[:n_documents]

    total_context = ""
    sources = ""
    for _, source, context in chosen:
        total_context = f"{total_context}{context}\n"
        sources = f"{sources}{source}\n"

    chat_message = f"{message}\n\nReading from:\n\n{sources}"
    message = f"{total_context}\n{message}"

    return message, chat_message


class VectorStore:
    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        self.directory = CONTEXT_DIRECTORY
        self.db_name = DB_NAME
        self.vector_file = VECTOR_NAME

    async def create(self, root: Path):
        assert root.exists(), f"{root} does not exist. Aborting."
        assert root.is_dir(), f"{root} is not a directory. Aborting."
        self.root = root
        assert (
            not self.rtfm_path.exists()
        ), f"Already initialized in {root}. Delete {self.rtfm_path} to be able to recreate the store."
        self.rtfm_path.mkdir()

        self.model = SentenceTransformer(self.MODEL, trust_remote_code=False)
        splitter = FileSplitter()
        relevant_sources = [subpath for ext in splitter.SUPPORTED_EXTENSIONS for subpath in root.rglob(f"*{ext}")]

        chunked = ((chunk, source) for source in relevant_sources for chunk in splitter.chunk_contents(source))

        async with aiosqlite.connect(self.db_path) as connection:
            await queries.create_document_table(connection)
            for i, (chunk, source) in enumerate(chunked):
                await queries.add_document(
                    connection,
                    source=str(source.resolve()),
                    text=chunk,
                    row_index=i,
                )

            await asyncio.wait_for(connection.commit(), timeout=None)
            n_documents = await queries.get_number_of_documents(connection)
            n_documents = n_documents[0][0]

            (embedding_len,) = self.embeddings("test").shape
            self.vectors = np.memmap(
                self.embedding_path,
                dtype="float32",
                shape=(n_documents, embedding_len),
                mode="w+",
            )

            async with queries.get_all_documents_cursor(connection) as cursor:
                progress = tqdm(total=n_documents)
                async for row_index, _, text in cursor:
                    progress.update()
                    self.vectors[row_index, :] = self.embeddings(text)

    async def load(self, root: Path) -> None:
        self.model = SentenceTransformer(self.MODEL, trust_remote_code=False)
        self.root = root
        async with aiosqlite.connect(self.db_path) as connection:
            (embedding_len,) = self.embeddings("test").shape
            n_documents = await queries.get_number_of_documents(connection)
            n_documents = n_documents[0][0]
            self.vectors = np.memmap(
                self.embedding_path,
                dtype="float32",
                shape=(n_documents, embedding_len),
                mode="r+",
            )

    async def get_nearest(
        self,
        text: str,
        n_nearest: int = 1,
    ) -> Iterable[Tuple[float, str, str]]:
        embeddings = self.embeddings(text)[None, ...]
        distances = euclidean_distances(self.vectors, embeddings).reshape(-1)
        best_records = np.argpartition(distances, kth=n_nearest)[:n_nearest]
        best_records = best_records.tolist()
        async with aiosqlite.connect(self.db_path) as connection:
            for record_index in best_records:
                document = await queries.get_document(connection, int(record_index))
                yield float(distances[record_index]), *(document[0])

    @property
    def db_path(self):
        return self.rtfm_path / self.db_name

    @property
    def embedding_path(self):
        return self.rtfm_path / self.vector_file

    @property
    def rtfm_path(self):
        return self.root / self.directory

    def embeddings(self, text: str) -> np.ndarray:
        return self.model.encode(text)


class FileSplitter:
    SUPPORTED_EXTENSIONS = [".txt", ".html"]
    MAX_CHARACTERS = 1200

    def __init__(self):
        self.splitter = TextSplitter(self.MAX_CHARACTERS)

    def chunk_contents(self, path: Path) -> Sequence[str]:
        text = path.read_text()
        if path.suffix == ".html":
            text = get_text(text)
        return self.splitter.chunks(text)


embedding_sqlite = """
-- name: create_document_table
CREATE TABLE IF NOT EXISTS "documents" (
    "source"        TEXT        NOT NULL,
    "text"          TEXT        NOT NULL,
    "row_index"     INTEGER,
    PRIMARY KEY("row_index")
);

-- name: add_document
INSERT OR REPLACE INTO documents(source, text, row_index) 
VALUES(:source, :text, :row_index);

-- name: get_document
SELECT source, text FROM documents WHERE row_index = :row_index;

-- name: get_all_documents
SELECT row_index, source, text FROM documents;

-- name: get_number_of_documents
SELECT COUNT(*) FROM documents;
"""
queries = aiosql.from_str(embedding_sqlite, "aiosqlite")

if __name__ == "__main__":
    asyncio.run(get_output())
