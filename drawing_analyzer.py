import pathlib
import re
import os
from aws_client import BedrockClient
from utils import create_dirs, get_pdf_name
from config import TEMP_DIR, OUTPUT_DIR

def extract_context_for_drawing(md_content, page_num=None):
    """마크다운 내용에서 도면에 대한 컨텍스트 정보 추출
    
    Args:
        md_content: 마크다운 파일 내용
        page_num: 도면 페이지 번호 (선택적)
        
    Returns:
        str: 추출된 컨텍스트 정보
    """
    # 전체 텍스트가 컨텍스트에 필요한 경우
    if page_num is None:
        return md_content
    
    # 페이지별로 분리
    page_pattern = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
    page_matches = list(page_pattern.finditer(md_content))
    
    if not page_matches:
        return md_content
    
    # 해당 페이지 전후의 컨텍스트 추출
    context = ""
    
    # 이전 페이지 컨텍스트 (최대 1페이지)
    prev_page = page_num - 1
    if prev_page >= 0:
        for i, match in enumerate(page_matches):
            if int(match.group(1)) == prev_page:
                start_idx = match.end()
                end_idx = page_matches[i+1].start() if i+1 < len(page_matches) else len(md_content)
                prev_context = md_content[start_idx:end_idx].strip()
                context += f"이전 페이지 내용:\n{prev_context}\n\n"
    
    # 다음 페이지 컨텍스트 (최대 1페이지)
    next_page = page_num + 1
    for i, match in enumerate(page_matches):
        if int(match.group(1)) == next_page:
            start_idx = match.end()
            end_idx = page_matches[i+1].start() if i+1 < len(page_matches) else len(md_content)
            next_context = md_content[start_idx:end_idx].strip()
            context += f"다음 페이지 내용:\n{next_context}"
    
    return context.strip()

def analyze_drawing(drawing_path, md_path=None, page_num=None):
    """도면 이미지 분석 수행
    
    Args:
        drawing_path: 도면 이미지 경로
        md_path: 마크다운 파일 경로 (선택적, 컨텍스트 추출용)
        page_num: 도면 페이지 번호 (선택적)
        
    Returns:
        dict: 분석 결과
    """
    try:
        # 컨텍스트 정보 추출 (마크다운 경로가 제공된 경우)
        context = None
        if md_path and md_path.exists():
            md_content = md_path.read_text(encoding='utf-8')
            context = extract_context_for_drawing(md_content, page_num)
        
        # Bedrock 클라이언트 생성
        bedrock_client = BedrockClient()
        
        # 도면 분석 (Langchain 사용)
        print(f"도면 분석 중: {drawing_path}")
        result = bedrock_client.analyze_drawing_with_nova_langchain(drawing_path, context)
        
        if result.get("success", False):
            print("도면 분석 완료")
            return {
                "drawing_path": str(drawing_path),
                "analysis": result["analysis"],
                "page_num": page_num
            }
        else:
            print(f"도면 분석 실패: {result.get('error', '알 수 없는 오류')}")
            return {
                "drawing_path": str(drawing_path),
                "analysis": "도면 분석에 실패했습니다.",
                "error": result.get("error", "알 수 없는 오류"),
                "page_num": page_num
            }
    
    except Exception as e:
        print(f"도면 분석 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "drawing_path": str(drawing_path),
            "analysis": "도면 분석 중 오류가 발생했습니다.",
            "error": str(e),
            "page_num": page_num
        }

def analyze_drawings(drawing_items, md_path=None, page_nums=None):
    """여러 도면 이미지 분석
    
    Args:
        drawing_items: 도면 이미지 정보 리스트 (경로만 있는 문자열 리스트 또는 {'path': 경로, 'page_num': 번호} 딕셔너리 리스트)
        md_path: 마크다운 파일 경로 (선택적)
        page_nums: 도면 페이지 번호 리스트 (선택적, drawing_items가 경로 문자열 리스트인 경우에만 사용)
        
    Returns:
        list: 분석 결과 리스트
    """
    results = []
    
    # 각 도면 분석
    for item in drawing_items:
        if isinstance(item, dict):
            # drawing_items가 딕셔너리 리스트인 경우
            drawing_path = item['path']
            page_num = item.get('page_num')
        else:
            # drawing_items가 문자열 리스트인 경우 (하위 호환성)
            drawing_path = item
            idx = drawing_items.index(item)
            page_num = page_nums[idx] if page_nums and idx < len(page_nums) else None
        
        result = analyze_drawing(drawing_path, md_path, page_num)
        results.append(result)
    
    return results

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("사용법: python drawing_analyzer.py <drawing_image> [md_path] [page_num]")
        sys.exit(1)
    
    drawing_path = pathlib.Path(sys.argv[1])
    if not drawing_path.exists():
        print(f"오류: 이미지 {drawing_path}이(가) 존재하지 않습니다")
        sys.exit(1)
    
    # 마크다운 경로 (선택적)
    md_path = None
    if len(sys.argv) > 2:
        md_path_str = sys.argv[2]
        if md_path_str != "None":
            md_path = pathlib.Path(md_path_str)
    
    # 페이지 번호 (선택적)
    page_num = None
    if len(sys.argv) > 3:
        try:
            page_num_str = sys.argv[3]
            if page_num_str != "None":
                page_num = int(page_num_str)
        except ValueError:
            print(f"오류: 잘못된 페이지 번호 형식: {sys.argv[3]}")
            sys.exit(1)
    
    result = analyze_drawing(drawing_path, md_path, page_num)
    print("\n도면 분석 결과:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
