
import re
import xml.etree.ElementTree as ET
from shared.db.d1 import D1Client

class WelfareProcessor:
    def __init__(self, d1_client: D1Client = None):
        self.d1 = d1_client or D1Client()

    def parse_and_save(self, policy_id, raw_xml):
        """
        Parses raw XML and saves to t_welfare_policies, t_welfare_conditions, t_welfare_categories.
        """
        try:
            root = ET.fromstring(raw_xml)
            
            # 1. Extract Basic Info
            title = self._get_text(root, ".//servNm")
            ministry = self._get_text(root, ".//jurMnofNm")
            summary = self._get_text(root, ".//servDgst")
            
            # Content: Combine target details and selection criteria for full context
            tgtr_dtl = self._get_text(root, ".//tgtrDtlCn")
            slct_crit = self._get_text(root, ".//slctCritCn")
            content = f"Target:\n{tgtr_dtl}\n\nCriteria:\n{slct_crit}"

            url = self._get_text(root, ".//servDtlLink") # Sometimes in different tags, simplified here
            
            # 2. Parse Conditions
            conditions = self._extract_conditions(content)
            
            # 3. Parse Categories
            categories = self._extract_categories(content, title)

            # 4. Prepare SQL Queries
            queries = []

            # Upsert Policy
            sql_policy = """
            INSERT INTO t_welfare_policies (policy_id, title, ministry, summary, content, url, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(policy_id) DO UPDATE SET
                title=excluded.title,
                ministry=excluded.ministry,
                summary=excluded.summary,
                content=excluded.content,
                last_updated=excluded.last_updated;
            """
            queries.append({"sql": sql_policy, "params": [policy_id, title, ministry, summary, content, url]})

            # Delete existing conditions/categories for this policy (full refresh strategy)
            queries.append({"sql": "DELETE FROM t_welfare_conditions WHERE policy_id = ?", "params": [policy_id]})
            queries.append({"sql": "DELETE FROM t_welfare_categories WHERE policy_id = ?", "params": [policy_id]})

            # Insert Conditions
            sql_cond = """
            INSERT INTO t_welfare_conditions (
                policy_id, age_min, age_max, gender, region, 
                employment_status, disability_yn, pregnancy_birth_yn, childcare_yn
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            queries.append({"sql": sql_cond, "params": [
                policy_id, 
                conditions.get('age_min'), 
                conditions.get('age_max'), 
                conditions.get('gender', 'ALL'), 
                conditions.get('region', 'Nationwide'),
                conditions.get('employment_status'),
                conditions.get('disability_yn', 'N'),
                conditions.get('pregnancy_birth_yn', 'N'),
                conditions.get('childcare_yn', 'N')
            ]})

            # Insert Categories
            sql_cat = "INSERT INTO t_welfare_categories (policy_id, category_name) VALUES (?, ?)"
            for cat in categories:
                queries.append({"sql": sql_cat, "params": [policy_id, cat]})

            # Execute
            self.d1.execute_batch(queries)
            # print(f"Processed {policy_id}: {title}")
            return True

        except ET.ParseError:
            print(f"Error parsing XML for {policy_id}")
            return False
        except Exception as e:
            print(f"Error processing {policy_id}: {e}")
            return False

    def _get_text(self, root, xpath):
        node = root.find(xpath)
        return node.text.strip() if node is not None and node.text else ""

    def _extract_conditions(self, text):
        cond = {}
        
        # Age extraction (Simple Regex for "만 XX세" or "XX세")
        # Finds patterns like "만 65세 이상", "18세 미만", "60세~"
        # This is a heuristic.
        text_normalized = text.replace(" ", "")
        
        age_min = None
        age_max = None
        
        # Regex for "Man 60 years or older" -> Min Age 60
        match_min = re.search(r'만?(\d+)세이상', text_normalized)
        if match_min:
            age_min = int(match_min.group(1))

        # Regex for "Under 18 years" -> Max Age 18
        match_max = re.search(r'만?(\d+)세미만', text_normalized)
        if match_max:
            age_max = int(match_max.group(1)) - 1 # Under 18 means max 17 (integer) or use < logic. Let's say max 17.

        # Range "18세~34세"
        match_range = re.search(r'만?(\d+)세[~-]만?(\d+)세', text_normalized)
        if match_range:
            age_min = int(match_range.group(1))
            age_max = int(match_range.group(2))

        if age_min: cond['age_min'] = age_min
        if age_max: cond['age_max'] = age_max

        # Gender
        if "여성" in text or "임신부" in text or "산모" in text:
            cond['gender'] = 'F'
        elif "남성" in text:
            cond['gender'] = 'M'
        else:
            cond['gender'] = 'ALL'

        # Region (Major Cities/Provinces)
        regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        found_regions = [r for r in regions if r in text]
        if found_regions:
            cond['region'] = ",".join(found_regions) # Store as comma separated if multiple, or just first?
            # For simplicity, if multiple, store "Specific". If one, store name. 
            # Ideally Many-to-Many, but schema uses single column text.
            # Let's clean up: matching "경기도" logic etc.
        else:
            cond['region'] = 'Nationwide'

        # Situations
        cond['pregnancy_birth_yn'] = 'Y' if any(x in text for x in ["임신", "출산", "산모", "난임"]) else 'N'
        cond['childcare_yn'] = 'Y' if any(x in text for x in ["영유아", "아동", "보육", "자녀", "양육"]) else 'N'
        cond['disability_yn'] = 'Y' if "장애" in text else 'N'
        
        if "구직" in text or "실직" in text or "미취업" in text:
            cond['employment_status'] = 'Unemployed'
        elif "자영업" in text or "소상공인" in text:
            cond['employment_status'] = 'Self-employed'
        
        return cond

    def _extract_categories(self, text, title):
        cats = set()
        combined = text + title
        
        mapping = {
            "Housing": ["주거", "전세", "월세", "임대", "주택"],
            "Medical": ["의료", "건강", "검진", "수술", "진료"],
            "Education": ["교육", "장학", "학비", "급식"],
            "Loan": ["융자", "대출", "보증"],
            "Startup": ["창업", "사업화"],
            "Culture": ["문화", "예술", "여가", "여행"]
        }
        
        for cat, keywords in mapping.items():
            if any(k in combined for k in keywords):
                cats.add(cat)
                
        if not cats:
            return ["Other"]

        return list(cats)
