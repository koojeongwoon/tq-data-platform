"""RAG Service for welfare policy chatbot

Retrieves relevant policies using QdrantService hybrid search and generates LLM responses.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from shared.config.settings import settings
from shared.db.postgres import PostgresClient
from shared.prompts import WELFARE_SYSTEM_PROMPT, build_rag_user_message
from shared.services.qdrant_service import QdrantService


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

        # Hybrid search in Qdrant
        results = self.qdrant.hybrid_search(
            query=query,
            limit=top_k,
            chunk_type=chunk_type,
            province=province
        )

        # Enrich with full policy data from PostgreSQL if needed
        enriched_results = []
        seen_policies = set()

        for result in results:
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
                # Fallback to chunk data only
                enriched_results.append({
                    "policy_id": policy_id or "",
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

        return enriched_results

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
        model: str = "gpt-4o-mini"
    ) -> Dict[str, Any]:
        """
        Main chat interface - retrieves context and generates response

        Args:
            query: User's question
            filters: Optional filters for policy search
            top_k: Number of policies to retrieve
            model: LLM model to use

        Returns:
            Response dict with answer and source policies (full data for frontend cards)
        """
        # 1. Retrieve relevant policies
        policies = self.retrieve_context(query, filters, top_k)

        # 2. Build context
        context = self.build_context_prompt(policies)

        # 3. Generate response
        answer = self.generate_response(query, context, model)

        # 4. Return structured response with full policy data
        return {
            "answer": answer,
            "sources": policies,  # Return full policy data for frontend card formatting
            "query": query,
            "context_used": len(policies) > 0
        }
