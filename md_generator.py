import pathlib
import re
import os
import shutil
from aws_client import BedrockClient
from utils import create_dirs, get_pdf_name, ensure_unique_filename
from config import TEMP_DIR, OUTPUT_DIR, CHUNK_SIZE

def insert_drawing_analysis(md_content, drawing_results):
    """마크다운 내용에 도면 분석 결과 삽입
    
    Args:
        md_content: 원본 마크다운 내용
        drawing_results: 도면 분석 결과 리스트
        
    Returns:
        str: 도면 분석이 포함된 마크다운 내용
    """
    # 도면 분석 결과가 없으면 원본 반환
    if not drawing_results:
        return md_content
    
    # 필요한 디렉토리 생성
    temp_dir, output_dir = create_dirs()
        
    # 도면 결과를 페이지 번호 기준으로 정렬
    drawing_results.sort(key=lambda x: x.get('page_num', -1) if x.get('page_num') is not None else -1)
    
    # 각 도면 이미지를 output 디렉토리로 복사하고 경로 및 분석 결과 추출
    drawing_info = {}
    for result in drawing_results:
        drawing_path = result.get('drawing_path')
        if not drawing_path:
            continue
            
        drawing_path = pathlib.Path(drawing_path)
        page_num = result.get('page_num')
        analysis = result.get('analysis', '도면 분석 결과 없음')
        
        # 페이지 번호가 없는 경우 파일명에서 추출 시도
        if page_num is None:
            page_match = re.search(r'page_(\d+)', drawing_path.name)
            if page_match:
                page_num = int(page_match.group(1))
        
        # 도면 이미지를 output 디렉토리로 복사 (상대 경로 접근을 위해)
        output_image_path = output_dir / drawing_path.name
        try:
            shutil.copy2(drawing_path, output_image_path)
            print(f"도면 이미지 복사: {drawing_path} -> {output_image_path}")
        except Exception as e:
            print(f"도면 이미지 복사 중 오류: {str(e)}")
        
        drawing_info[drawing_path.name] = {
            'path': f"./{drawing_path.name}",  # 상대 경로로 변경
            'page_num': page_num,
            'analysis': analysis
        }
    
    # 마크다운에 도면 이미지와 분석 결과 삽입
    new_content = md_content
    
    # PDF에서 추출된 페이지 구분자가 있는지 확인
    has_page_markers = "<!-- page " in new_content
    
    # 페이지 번호가 있는 경우 해당 페이지 끝에 도면 삽입
    for drawing_name, info in drawing_info.items():
        page_num = info.get('page_num')
        path = info.get('path')
        analysis = info.get('analysis')
        
        # 도면 이미지와 분석 내용
        drawing_md = f"\n\n## 도면 {page_num+1}\n\n"
        drawing_md += f"![도면 이미지]({path})\n\n"
        drawing_md += f"### 도면 분석 결과\n\n{analysis}\n\n"
        
        if page_num is not None and has_page_markers:
            # 페이지 마커가 있고 페이지 번호가 있는 경우 해당 페이지 끝에 추가
            page_pattern = f"<!-- page {page_num} -->"
            next_page_match = re.search(f"<!-- page {page_num+1} -->", new_content)
            
            if page_pattern in new_content:
                if next_page_match:
                    # 현재 페이지와 다음 페이지 사이에 삽입
                    insert_pos = next_page_match.start()
                    new_content = new_content[:insert_pos] + drawing_md + new_content[insert_pos:]
                else:
                    # 문서 끝에 추가
                    new_content += drawing_md
            else:
                # 페이지 마커는 있지만 현재 페이지 마커가 없는 경우
                new_content += f"\n\n<!-- page {page_num} 도면 -->\n" + drawing_md
        else:
            # 페이지 마커가 없거나 페이지 번호가 없는 경우 문서 끝에 추가
            new_content += drawing_md
    
    return new_content

def generate_markdown(md_path, drawing_results, output_path=None):
    """최종 마크다운 문서 생성
    
    Args:
        md_path: 초기 마크다운 파일 경로
        drawing_results: 도면 분석 결과 리스트
        output_path: 출력 파일 경로 (선택적)
        
    Returns:
        pathlib.Path: 생성된 마크다운 파일 경로
    """
    try:
        # 디렉토리 생성
        _, output_dir = create_dirs()
        
        # 기본 경로 설정 - 항상 원본 이름 사용 (중복 파일명 생성 방지)
        if output_path is None:
            pdf_name = get_pdf_name(md_path)
            output_path = output_dir / f"{pdf_name}.md"
            # 파일이 이미 존재하더라도 덮어쓰기 (unique 파일명 생성 하지 않음)
        
        # 원본 마크다운 내용 읽기
        md_content = md_path.read_text(encoding='utf-8')
        
        # 도면 분석 결과 삽입
        enhanced_content = insert_drawing_analysis(md_content, drawing_results)
        
        # Claude로 최종 마크다운 최적화
        bedrock_client = BedrockClient()
        pdf_name = get_pdf_name(md_path)
        final_content = bedrock_client.generate_markdown_with_claude(enhanced_content, pdf_name)
        
        if final_content:
            output_path.write_text(final_content, encoding='utf-8')
            print(f"최종 마크다운 생성: {output_path}")
        else:
            # Claude 처리 실패 시 중간 결과 저장
            output_path.write_text(enhanced_content, encoding='utf-8')
            print(f"Claude 처리 실패, 중간 결과 저장: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"마크다운 생성 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 오류 발생 시 중간 결과라도 저장
        try:
            if 'enhanced_content' in locals():
                output_path.write_text(enhanced_content, encoding='utf-8')
                print(f"오류 발생, 중간 결과 저장: {output_path}")
                return output_path
        except:
            pass
            
        return None

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 3:
        print("사용법: python md_generator.py <md_file> <drawing_results_json>")
        print("drawing_results_json: 도면 분석 결과를 담은 JSON 파일 경로")
        sys.exit(1)
    
    md_path = pathlib.Path(sys.argv[1])
    if not md_path.exists():
        print(f"오류: 파일 {md_path}이(가) 존재하지 않습니다")
        sys.exit(1)
    
    drawing_results_path = pathlib.Path(sys.argv[2])
    if not drawing_results_path.exists():
        print(f"오류: 파일 {drawing_results_path}이(가) 존재하지 않습니다")
        sys.exit(1)
    
    with open(drawing_results_path, 'r', encoding='utf-8') as f:
        drawing_results = json.load(f)
    
    output_path = generate_markdown(md_path, drawing_results)
    if output_path:
        print(f"마크다운 생성 완료: {output_path}")
    else:
        print("마크다운 생성 실패")
        sys.exit(1)
