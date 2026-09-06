import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from src.shared.config import get_settings
from src.model_gateway.execution_manager import execution_manager

async def main():
    client = QdrantClient(host="qdrant", port=6333)
    query_embedding = await execution_manager.generate_embedding(
        text="Who acquired Cvent and for how much?",
        model_id="embedding-gemini",
    )
    tags = ["public", "general", "engineering", "finance", "operations", "reports", "classified"]
    tag_filter = Filter(
        must=[
            FieldCondition(
                key="access_tag",
                match=MatchAny(any=tags),
            )
        ]
    )
    results = client.query_points(
        collection_name=get_settings().qdrant_collection,
        query=query_embedding,
        query_filter=tag_filter,
        limit=5,
    ).points
    
    print(f"Matched {len(results)} points")
    for r in results:
        print(f"Score: {r.score}, Doc: {r.payload.get('document_title')}")

asyncio.run(main())
