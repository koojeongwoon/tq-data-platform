
from app.services.processor import WelfareProcessor
import xml.etree.ElementTree as ET

# Mock D1 Client to capture queries instead of sending to API
class MockD1Client:
    def __init__(self):
        self.queries_log = []

    def execute_batch(self, queries):
        self.queries_log.extend(queries)
        return {"success": True}
        
    def init_db(self):
        pass

def test_parsing():
    processor = WelfareProcessor(d1_client=MockD1Client())
    
    # Sample 1: Elderly in Seoul (Korean Text)
    sample_xml_1 = """
    <wantedDtl>
        <servId>TEST001</servId>
        <servNm>서울시 어르신 지원</servNm>
        <jurMnofNm>서울시</jurMnofNm>
        <servDgst>서울시 거주 만 65세 이상 지원</servDgst>
        <tgtrDtlCn>서울시에 거주하는 만 65세 이상 어르신.</tgtrDtlCn>
        <slctCritCn>주민등록상 서울시 거주자. 만 65세 이상.</slctCritCn>
        <servDtlLink>http://example.com</servDtlLink>
    </wantedDtl>
    """
    
    print("Testing Sample 1 (Elderly/Seoul)...")
    processor.parse_and_save("TEST001", sample_xml_1)
    
    # Inspect captured queries for Sample 1
    log = processor.d1.queries_log
    
    # Find INSERT into t_welfare_conditions
    cond_query = next(q for q in log if "INSERT INTO t_welfare_conditions" in q['sql'])
    params = cond_query['params']
    print(f"Captured Params: {params}")
    
    # Expected: [policy_id, age_min, age_max, gender, region, emp, dis, preg, child]
    # Indices:    0          1        2        3       4       5    6    7     8
    # age_min should be 65 (index 1)
    assert params[1] == 65, f"Expected age_min=65, got {params[1]}"
    # Region should be '서울' (index 4)
    assert params[4] == "서울", f"Expected region='서울', got {params[4]}"
    
    print("Sample 1 Passed!\n")

    # Sample 2: Pregnancy
    sample_xml_2 = """
    <wantedDtl>
        <servId>TEST002</servId>
        <servNm>임신부 지원</servNm>
        <tgtrDtlCn>임신부 및 출산 가정.</tgtrDtlCn>
        <slctCritCn>임신부 누구나.</slctCritCn>
        <servDtlLink>http://example.com</servDtlLink>
    </wantedDtl>
    """
    
    print("Testing Sample 2 (Pregnancy)...")
    try:
        processor.parse_and_save("TEST002", sample_xml_2)
        log = processor.d1.queries_log
        # Get the latest insert
        cond_query = [q for q in log if "INSERT INTO t_welfare_conditions" in q['sql']][-1]
        params = cond_query['params']
        print(f"Captured Params: {params}")
        
        assert params[3] == 'F', f"Expected gender='F', got {params[3]}"
        assert params[7] == 'Y', f"Expected pregnancy_birth_yn='Y', got {params[7]}"
        print("Sample 2 Passed!\n")
    except Exception as e:
        print(f"Sample 2 Failed: {e}")

if __name__ == "__main__":
    test_parsing()
