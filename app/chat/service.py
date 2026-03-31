"""RAG Service for welfare policy chatbot

Retrieves relevant policies using QdrantService hybrid search and generates LLM responses.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from shared.config.settings import settings
from shared.db.postgres import PostgresClient
from app.welfare.prompts import WELFARE_SYSTEM_PROMPT, build_rag_user_message
from shared.services.qdrant_service import QdrantService
from flashrank import Ranker, RerankRequest


class RAGService:
    """RAG-based chatbot service using QdrantService (hybrid search) + PostgreSQL + OpenAI"""

    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        """
        Initialize RAG service

        Args:
            qdrant_service: Pre-loaded QdrantService instance (optional)
                           If not provided, creates a new instance
        """
        if qdrant_service:
            self.qdrant = qdrant_service
        else:
            self.qdrant = QdrantService(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT
            )

        self.postgres = PostgresClient()

        # OpenAI client
        if settings.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            self.openai_client = None

        # Initialize Reranker (Lightweight Model)
        # cache_dir ensures model is downloaded once
        self.ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="./.cache")

    def retrieve_context(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant policy chunks using hybrid search (dense + sparse)

        Args:
            query: User's question
            filters: Optional filters (chunk_type, province)
            top_k: Number of results to retrieve

        Returns:
            List of relevant policy chunks with metadata
        """
        # Extract filter parameters
        chunk_type = filters.get("chunk_type") if filters else None
        province = filters.get("province") or filters.get("ctpv_nm") if filters else None
        life_cycle = filters.get("life_cycle") if filters else None

        # Hybrid search in Qdrant
        # 1. Fetch more candidates for reranking (e.g., 4x top_k)
        fetch_k = top_k * 4
        
        candidates = self.qdrant.hybrid_search(
            query=query,
            limit=fetch_k,
            chunk_type=chunk_type,
            province=province,
            life_cycle=life_cycle
        )

        if not candidates:
            return []

        # 2. Rerank using FlashRank
        passages = [
            {
                "id": c.get("policy_id") or str(i),
                "text": f"{c.get('title', '')} {c.get('content', '')}",
                "meta": c
            }
            for i, c in enumerate(candidates)
        ]

        rerank_request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(rerank_request)
        
        # Take top_k from reranked results
        reranked_candidates = [r["meta"] for r in results[:top_k]]
        
        # Update scores in candidates
        for i, r in enumerate(results[:top_k]):
             reranked_candidates[i]["score"] = float(r["score"])

        # Enrich with full policy data from PostgreSQL if needed
        enriched_results = []
        seen_policies = set()

        for result in reranked_candidates:
            policy_id = result.get("policy_id")

            # Get full policy details from PostgreSQL (deduplicate)
            if policy_id and policy_id not in seen_policies:
                full_policy = self.postgres.get_policy_by_id(policy_id)
                seen_policies.add(policy_id)

                if full_policy:
                    enriched_results.append({
                        "policy_id": policy_id,
                        "score": result.get("score", 0),
                        "chunk_type": result.get("chunk_type", ""),
                        "chunk_content": result.get("content", ""),
                        "title": full_policy.get("title", result.get("title", "")),
                        "ministry": full_policy.get("ministry", ""),
                        "summary": full_policy.get("summary", ""),
                        "support_content": full_policy.get("support_content", ""),
                        "target_detail": full_policy.get("target_detail", ""),
                        "application_method": full_policy.get("application_method", ""),
                        "application_detail": full_policy.get("application_detail", ""),
                        "phone": full_policy.get("phone", ""),
                        "website": full_policy.get("website", ""),
                        "source_type": full_policy.get("source_type", ""),
                        "ctpv_nm": full_policy.get("ctpv_nm", ""),
                        "sgg_nm": full_policy.get("sgg_nm", ""),
                    })
                else:
                    # Fallback to chunk data if DB lookup fails but ID is valid and new
                    enriched_results.append({
                        "policy_id": policy_id,
                        "score": result.get("score", 0),
                        "chunk_type": result.get("chunk_type", ""),
                        "chunk_content": result.get("content", ""),
                        "title": result.get("title", ""),
                        "ministry": "",
                        "summary": "",
                        "support_content": "",
                        "target_detail": "",
                        "application_method": "",
                        "application_detail": "",
                        "phone": "",
                        "website": "",
                        "source_type": "",
                        "ctpv_nm": "",
                        "sgg_nm": "",
                    })
            elif not policy_id:
                # Add points without policy_id (e.g., general chunks)
                enriched_results.append({
                    "policy_id": "",
                    "score": result.get("score", 0),
                    "chunk_type": result.get("chunk_type", ""),
                    "chunk_content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "ministry": "",
                    "summary": "",
                    "support_content": "",
                    "target_detail": "",
                    "application_method": "",
                    "application_detail": "",
                    "phone": "",
                    "website": "",
                    "source_type": "",
                    "ctpv_nm": "",
                    "sgg_nm": "",
                })
            # If policy_id in seen_policies, we skip it (deduplication)

        return enriched_results

    def retrieve_context_by_id(self, policy_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve a specific policy by ID from PostgreSQL
        
        Args:
            policy_id: The ID of the policy to retrieve
            
        Returns:
            List containing the single policy dict if found, else empty list
        """
        full_policy = self.postgres.get_policy_by_id(policy_id)
        if not full_policy:
            return []
            
        return [{
            "policy_id": policy_id,
            "score": 1.0,  # Max score for exact match
            "chunk_type": "full",
            "chunk_content": full_policy.get("support_content", "") or full_policy.get("summary", ""),
            "title": full_policy.get("title", ""),
            "ministry": full_policy.get("ministry", ""),
            "summary": full_policy.get("summary", ""),
            "support_content": full_policy.get("support_content", ""),
            "target_detail": full_policy.get("target_detail", ""),
            "application_method": full_policy.get("application_method", ""),
            "application_detail": full_policy.get("application_detail", ""),
            "phone": full_policy.get("phone", ""),
            "website": full_policy.get("website", ""),
            "source_type": full_policy.get("source_type", ""),
            "ctpv_nm": full_policy.get("ctpv_nm", ""),
            "sgg_nm": full_policy.get("sgg_nm", ""),
        }]

    def build_context_prompt(self, policies: List[Dict[str, Any]]) -> str:
        """
        Build context string from retrieved policies

        Args:
            policies: List of policy documents

        Returns:
            Formatted context string for LLM
        """
        if not policies:
            return "관련 복지 정책 정보를 찾지 못했습니다."

        context_parts = []
        for i, policy in enumerate(policies, 1):
            parts = [f"[정책 {i}]"]
            parts.append(f"정책명: {policy.get('title', '정보 없음')}")

            if policy.get("ministry"):
                parts.append(f"담당부처: {policy['ministry']}")

            if policy.get("ctpv_nm"):
                region = policy["ctpv_nm"]
                if policy.get("sgg_nm"):
                    region += f" {policy['sgg_nm']}"
                parts.append(f"지역: {region}")

            if policy.get("summary"):
                parts.append(f"요약: {policy['summary']}")

            if policy.get("support_content"):
                parts.append(f"지원내용: {policy['support_content']}")

            if policy.get("target_detail"):
                parts.append(f"지원대상: {policy['target_detail']}")

            if policy.get("application_method") or policy.get("application_detail"):
                method = policy.get("application_method", "")
                detail = policy.get("application_detail", "")
                parts.append(f"신청방법: {method} {detail}".strip())

            if policy.get("phone"):
                parts.append(f"문의전화: {policy['phone']}")

            if policy.get("website"):
                parts.append(f"홈페이지: {policy['website']}")

            # Include chunk content for additional context
            if policy.get("chunk_content"):
                parts.append(f"상세정보: {policy['chunk_content'][:500]}")

            context_parts.append("\n".join(parts))

        return "\n\n".join(context_parts)

    def generate_response(
        self,
        query: str,
        context: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1024
    ) -> str:
        """
        Generate LLM response based on query and context (non-streaming)

        Args:
            query: User's question
            context: Retrieved policy context
            model: OpenAI model to use
            max_tokens: Maximum response tokens

        Returns:
            Generated response text
        """
        if not self.openai_client:
            return "LLM 서비스가 설정되지 않았습니다. OPENAI_API_KEY를 확인해주세요."

        user_message = build_rag_user_message(query, context)

        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": WELFARE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"응답 생성 중 오류가 발생했습니다: {str(e)}"

    def generate_response_stream(
        self,
        query: str,
        context: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1024
    ):
        """
        Generate streaming LLM response based on query and context

        Args:
            query: User's question
            context: Retrieved policy context
            model: OpenAI model to use
            max_tokens: Maximum response tokens

        Yields:
            Response text chunks
        """
        if not self.openai_client:
            yield "LLM 서비스가 설정되지 않았습니다. OPENAI_API_KEY를 확인해주세요."
            return

        user_message = build_rag_user_message(query, context)

        try:
            stream = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": WELFARE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"응답 생성 중 오류가 발생했습니다: {str(e)}"

    def chat(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        model: str = "gpt-4o-mini",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Main chat interface with Semantic Caching
        
        1. Check semantic cache in Qdrant
        2. If hit, return cached answer
        3. If miss, perform RAG and save to cache
        """
        # 1. Semantic Cache Check
        if use_cache:
            cache_hit = self.qdrant.get_cache(query, threshold=settings.QDRANT_CACHE_THRESHOLD)
            if cache_hit:
                return {
                    "answer": cache_hit["answer"],
                    "sources": cache_hit["sources"],
                    "query": query,
                    "cache_hit": True,
                    "cache_score": cache_hit["score"]
                }

        # 2. Retrieve relevant policies (RAG)
        policies = self.retrieve_context(query, filters, top_k)

        # 3. Build context
        context = self.build_context_prompt(policies)

        # 4. Generate response
        answer = self.generate_response(query, context, model)

        # 5. Save to Semantic Cache
        if use_cache and answer:
            self.qdrant.upsert_cache(query, answer, policies)

        # 6. Return structured response
        return {
            "answer": answer,
            "sources": policies,
            "query": query,
            "context_used": len(policies) > 0,
            "cache_hit": False
        }

    def chat_stream(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        model: str = "gpt-4o-mini",
        use_cache: bool = True
    ):
        """
        Streaming chat interface with Semantic Caching
        """
        # 1. Semantic Cache Check
        if use_cache:
            cache_hit = self.qdrant.get_cache(query, threshold=settings.QDRANT_CACHE_THRESHOLD)
            if cache_hit:
                # Yield entire cached answer as a single "chunk"
                # We yield a dict to keep consistency with generated chunks if needed
                yield cache_hit["answer"]
                return

        # 2. Retrieve relevant policies (RAG)
        policies = self.retrieve_context(query, filters, top_k)

        # 3. Build context
        context = self.build_context_prompt(policies)

        # 4. Generate streaming response and collect for caching
        full_answer = ""
        for chunk in self.generate_response_stream(query, context, model):
            full_answer += chunk
            yield chunk

        # 5. Save to cache after stream completion
        if use_cache and full_answer:
            self.qdrant.upsert_cache(query, full_answer, policies)
