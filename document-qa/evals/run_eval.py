"""Run the labeled retrieval set with the configured OpenRouter models."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.documents import chunk_pages, extract_pages  # noqa: E402
from app.openrouter import OpenRouter  # noqa: E402
from app.retrieval import cosine_similarity  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", action="store_true", help="Also request a generated answer for every query with retrieved evidence (uses API credits).")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/latest-report.json")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.openrouter_api_key:
        parser.error("Set OPENROUTER_API_KEY in the environment or .env before running live evaluation.")
    provider = OpenRouter(settings)
    try:
        corpus = []
        for path in sorted((ROOT / "sample-documents").glob("*")):
            if path.suffix.lower() not in {".pdf", ".txt"}:
                continue
            pages = extract_pages(path.name, path.read_bytes(), settings.max_pdf_pages)
            chunks = chunk_pages(pages, settings.chunk_words, settings.chunk_overlap_words)
            vectors = []
            for start in range(0, len(chunks), 64):
                vectors.extend(provider.embed([chunk.content for chunk in chunks[start:start + 64]]))
            corpus.extend({"filename": path.name, "page": chunk.page_number, "text": chunk.content, "vector": vector}
                          for chunk, vector in zip(chunks, vectors))

        cases = json.loads((ROOT / "evals/queries.json").read_text())
        rows = []
        hit1 = hit5 = reciprocal_rank = unknown_abstain = 0
        for case in cases:
            query_vector = provider.embed([case["query"]])[0]
            ranked = sorted(
                ({**chunk, "score": cosine_similarity(query_vector, chunk["vector"])} for chunk in corpus),
                key=lambda item: item["score"], reverse=True,
            )
            expected = set(case["expected_sources"])
            rank = next((i for i, item in enumerate(ranked, 1) if item["filename"] in expected), None) if expected else None
            hit1 += int(rank == 1)
            hit5 += int(rank is not None and rank <= 5)
            reciprocal_rank += (1 / rank) if rank else 0
            best_score = ranked[0]["score"] if ranked else 0.0
            is_unknown = not expected
            threshold_abstain = best_score < settings.min_relevance_score
            unknown_abstain += int(is_unknown and threshold_abstain)
            row = {"id": case["id"], "query": case["query"], "expected_sources": sorted(expected),
                   "top_sources": [{"filename": item["filename"], "page": item["page"], "score": round(item["score"], 4)} for item in ranked[:5]],
                   "expected_rank": rank, "best_score": round(best_score, 4), "threshold_abstain": threshold_abstain}
            if args.answers and not threshold_abstain:
                passages = [{"source_id": item["filename"] + "#" + str(item["page"]), "filename": item["filename"], "page": item["page"], "text": item["text"]}
                            for item in ranked[:settings.top_k]]
                result = provider.answer(case["query"], [], passages)
                valid_ids = {item["source_id"] for item in passages}
                row["answer_review"] = {"answer": result["answer"], "model_abstained": result["abstain"],
                                         "citation_ids_valid": all(value in valid_ids for value in result["citation_ids"]),
                                         "human_support_review": "pending"}
            rows.append(row)

        labeled = sum(bool(case["expected_sources"]) for case in cases)
        unknown_count = len(cases) - labeled
        report = {
            "evaluation": "OpenRouter embedding retrieval evaluation",
            "embedding_model": settings.openrouter_embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "chat_model": settings.openrouter_chat_model if args.answers else None,
            "chunk_words": settings.chunk_words,
            "chunk_overlap_words": settings.chunk_overlap_words,
            "top_k": settings.top_k,
            "min_relevance_score": settings.min_relevance_score,
            "query_count": len(cases),
            "labeled_query_count": labeled,
            "recall_at_1": round(hit1 / labeled, 4) if labeled else None,
            "recall_at_5": round(hit5 / labeled, 4) if labeled else None,
            "mrr": round(reciprocal_rank / labeled, 4) if labeled else None,
            "unknown_answer_abstain_rate": round(unknown_abstain / unknown_count, 4) if unknown_count else None,
            "answer_support_requires_human_review": bool(args.answers),
            "results": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
        print(f"Detailed report: {args.output}")
    finally:
        provider.close()


if __name__ == "__main__":
    main()
