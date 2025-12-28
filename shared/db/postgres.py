"""PostgreSQL client for welfare policy keyword search"""

from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch

from shared.config.settings import settings


class PostgresClient:
    """PostgreSQL client for keyword-based welfare policy search"""

    def __init__(self):
        self.host = settings.POSTGRES_HOST
        self.port = settings.POSTGRES_PORT
        self.database = settings.POSTGRES_DB
        self.user = settings.POSTGRES_USER
        self.password = settings.POSTGRES_PASSWORD

        self._connection = None

    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string"""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            yield conn
            conn.commit()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"PostgreSQL error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def execute_query(self, sql: str, params: tuple = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SELECT query and return results as list of dicts

        Args:
            sql: SQL query string
            params: Query parameters (use %s placeholders)

        Returns:
            List of result rows as dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Query execution error: {e}")
            return None

    def execute_one(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return first result

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            Single result row as dictionary
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Query execution error: {e}")
            return None

    def execute_write(self, sql: str, params: tuple = None) -> bool:
        """
        Execute INSERT/UPDATE/DELETE query

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    return True
        except psycopg2.Error as e:
            print(f"Write execution error: {e}")
            return False

    def execute_batch_insert(self, sql: str, params_list: List[tuple]) -> bool:
        """
        Execute batch INSERT for better performance

        Args:
            sql: INSERT SQL with placeholders
            params_list: List of parameter tuples

        Returns:
            True if successful, False otherwise
        """
        if not params_list:
            return True

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    execute_batch(cursor, sql, params_list, page_size=100)
                    return True
        except psycopg2.Error as e:
            print(f"Batch insert error: {e}")
            return False

    def upsert_policy(self, policy_data: Dict[str, Any]) -> bool:
        """
        Insert or update a single welfare policy

        Args:
            policy_data: Dictionary with policy fields

        Returns:
            True if successful, False otherwise
        """
        sql = """
        INSERT INTO welfare_policies (
            policy_id, title, ministry, summary, source_type,
            ctpv_nm, sgg_nm, life_cycles, interest_themes,
            support_cycle, support_provision, support_content,
            target_group, target_detail, selection_criteria,
            application_method, application_detail,
            phone, website, start_date, end_date
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (policy_id) DO UPDATE SET
            title = EXCLUDED.title,
            ministry = EXCLUDED.ministry,
            summary = EXCLUDED.summary,
            source_type = EXCLUDED.source_type,
            ctpv_nm = EXCLUDED.ctpv_nm,
            sgg_nm = EXCLUDED.sgg_nm,
            life_cycles = EXCLUDED.life_cycles,
            interest_themes = EXCLUDED.interest_themes,
            support_cycle = EXCLUDED.support_cycle,
            support_provision = EXCLUDED.support_provision,
            support_content = EXCLUDED.support_content,
            target_group = EXCLUDED.target_group,
            target_detail = EXCLUDED.target_detail,
            selection_criteria = EXCLUDED.selection_criteria,
            application_method = EXCLUDED.application_method,
            application_detail = EXCLUDED.application_detail,
            phone = EXCLUDED.phone,
            website = EXCLUDED.website,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            last_updated = CURRENT_TIMESTAMP
        """

        params = (
            policy_data.get('policy_id'),
            policy_data.get('title'),
            policy_data.get('ministry'),
            policy_data.get('summary'),
            policy_data.get('source_type'),
            policy_data.get('ctpv_nm'),
            policy_data.get('sgg_nm'),
            policy_data.get('life_cycles', []),
            policy_data.get('interest_themes', []),
            policy_data.get('support_cycle'),
            policy_data.get('support_provision'),
            policy_data.get('support_content'),
            policy_data.get('target_group'),
            policy_data.get('target_detail'),
            policy_data.get('selection_criteria'),
            policy_data.get('application_method'),
            policy_data.get('application_detail'),
            policy_data.get('phone'),
            policy_data.get('website'),
            policy_data.get('start_date'),
            policy_data.get('end_date')
        )

        return self.execute_write(sql, params)

    def keyword_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based search with filters

        Args:
            query: Search query text
            filters: Optional filters (region, life_cycle, theme, etc.)
            limit: Maximum number of results

        Returns:
            List of matching policies
        """
        conditions = []
        params = []

        # Full-text search
        if query:
            conditions.append("search_vector @@ plainto_tsquery('simple', %s)")
            params.append(query)

        # Regional filter
        if filters:
            if filters.get('ctpv_nm'):
                conditions.append("ctpv_nm = %s")
                params.append(filters['ctpv_nm'])

            if filters.get('sgg_nm'):
                conditions.append("sgg_nm = %s")
                params.append(filters['sgg_nm'])

            # Life cycle filter
            if filters.get('life_cycle'):
                conditions.append("%s = ANY(life_cycles)")
                params.append(filters['life_cycle'])

            # Interest theme filter
            if filters.get('interest_theme'):
                conditions.append("%s = ANY(interest_themes)")
                params.append(filters['interest_theme'])

            # Source type filter
            if filters.get('source_type'):
                conditions.append("source_type = %s")
                params.append(filters['source_type'])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Add ranking if query exists
        if query:
            sql = f"""
            SELECT
                policy_id, title, ministry, summary, source_type,
                ctpv_nm, sgg_nm, life_cycles, interest_themes,
                support_content, target_detail, application_detail,
                phone, website,
                ts_rank(search_vector, plainto_tsquery('simple', %s)) as rank
            FROM welfare_policies
            WHERE {where_clause}
            ORDER BY rank DESC, title
            LIMIT %s
            """
            params = [query] + params + [limit]
        else:
            sql = f"""
            SELECT
                policy_id, title, ministry, summary, source_type,
                ctpv_nm, sgg_nm, life_cycles, interest_themes,
                support_content, target_detail, application_detail,
                phone, website
            FROM welfare_policies
            WHERE {where_clause}
            ORDER BY title
            LIMIT %s
            """
            params.append(limit)

        return self.execute_query(sql, tuple(params)) or []

    def get_policy_by_id(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single policy by ID

        Args:
            policy_id: Policy ID

        Returns:
            Policy data as dictionary
        """
        sql = "SELECT * FROM welfare_policies WHERE policy_id = %s"
        return self.execute_one(sql, (policy_id,))

    def get_existing_policy_ids(self) -> set:
        """
        Get set of all existing policy IDs

        Returns:
            Set of policy IDs
        """
        sql = "SELECT policy_id FROM welfare_policies"
        results = self.execute_query(sql)

        if results:
            return {row['policy_id'] for row in results}
        return set()

    def get_policies_by_region(self, ctpv_nm: str, sgg_nm: str = None) -> List[Dict[str, Any]]:
        """
        Get policies by region

        Args:
            ctpv_nm: Province/City name
            sgg_nm: District name (optional)

        Returns:
            List of policies
        """
        if sgg_nm:
            sql = "SELECT * FROM welfare_policies WHERE ctpv_nm = %s AND sgg_nm = %s"
            params = (ctpv_nm, sgg_nm)
        else:
            sql = "SELECT * FROM welfare_policies WHERE ctpv_nm = %s"
            params = (ctpv_nm,)

        return self.execute_query(sql, params) or []

    def count_policies(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count policies with optional filters

        Args:
            filters: Optional filters

        Returns:
            Count of policies
        """
        conditions = []
        params = []

        if filters:
            if filters.get('ctpv_nm'):
                conditions.append("ctpv_nm = %s")
                params.append(filters['ctpv_nm'])

            if filters.get('source_type'):
                conditions.append("source_type = %s")
                params.append(filters['source_type'])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT COUNT(*) as count FROM welfare_policies WHERE {where_clause}"

        result = self.execute_one(sql, tuple(params))
        return result['count'] if result else 0

    def health_check(self) -> bool:
        """
        Check if database connection is healthy

        Returns:
            True if connection is successful
        """
        try:
            result = self.execute_one("SELECT 1 as test")
            return result is not None
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
