import pathlib
import shutil
import re
import pymupdf4llm
import fitz  # PyMuPDF
from PIL import Image
import io
import numpy as np
from utils import create_dirs, get_pdf_name, ensure_unique_filename
from config import TEMP_DIR, LOW_RES_IMAGE_QUALITY, IMAGE_FORMAT
from aws_client import BedrockClient
from pdf2image import convert_from_path

def is_drawing_page(page, text_threshold=200, line_ratio_threshold=0.4):
    """페이지가 도면 페이지인지 판단
    
    Args:
        page: fitz.Page 객체
        text_threshold: 텍스트가 이 값보다 적으면 도면 가능성 증가
        line_ratio_threshold: 직선 비율이 이 값보다 높으면 도면 가능성 증가
        
    Returns:
        bool: 도면 페이지 여부
    """
    # 텍스트 양 확인
    text = page.get_text()
    if len(text) < text_threshold:
        # 텍스트가 적은 경우, 추가 확인
        
        # 직선 개수 확인 (간단한 휴리스틱)
        paths = page.get_drawings()
        if not paths:
            return False
            
        total_paths = 0
        straight_lines = 0
        
        for path in paths:
            for item in path['items']:
                total_paths += 1
                # 직선 판정 (시작점과 끝점만 있고 중간점이 없으면 직선)
                if item[0] == 'l' and len(item) == 2:
                    straight_lines += 1
        
        # 직선 비율 계산
        if total_paths > 0:
            straight_line_ratio = straight_lines / total_paths
            if straight_line_ratio > line_ratio_threshold:
                return True
                
    return False

def identify_drawing_pages_with_ai(pdf_path):
    """Langchain과 AI를 사용하여 PDF 파일에서 도면 페이지 식별
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        list: 도면 페이지 번호 리스트 (0-based)
    """
    temp_dir, _ = create_dirs()
    pdf_name = get_pdf_name(pdf_path)
    bedrock_client = BedrockClient()
    
    # PDF의 총 페이지 수 확인
    pdf_document = fitz.open(pdf_path)
    total_pages = len(pdf_document)
    pdf_document.close()
    
    # 모든 페이지를 저해상도 JPEG로 변환 (MIME 타입 문제 해결을 위해 PNG 대신 JPEG 사용)
    print(f"모든 페이지를 저해상도 JPEG로 변환 중...")
    images = convert_from_path(
        pdf_path,
        dpi=LOW_RES_IMAGE_QUALITY,
        fmt='JPEG'  # 항상 JPEG 형식 사용
    )
    
    drawing_pages = []
    
    for i, image in enumerate(images):
        # 이미지 임시 저장
        temp_image_path = temp_dir / f"{pdf_name}_page_{i}_preview.{IMAGE_FORMAT.lower()}"
        image.save(str(temp_image_path))
        
        print(f"페이지 {i+1}/{total_pages} Nova Lite로 이미지 분석 중...")
        
        # Langchain을 사용한 Nova Lite로 도면 여부 판별
        if bedrock_client.is_drawing_with_nova_lite_langchain(temp_image_path):
            drawing_pages.append(i)
            print(f"✓ 페이지 {i}가 도면으로 식별되었습니다.")
    
    return drawing_pages

def extract_page_content(pdf_path):
    """PDF 페이지 내용 추출 및 도면 페이지 식별 (휴리스틱 기반)
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        tuple: (일반 페이지 리스트, 도면 페이지 리스트)
    """
    pdf_document = fitz.open(pdf_path)
    regular_pages = []
    drawing_pages = []
    
    for i, page in enumerate(pdf_document):
        if is_drawing_page(page):
            drawing_pages.append(i)
        else:
            regular_pages.append(i)
            
    pdf_document.close()
    return regular_pages, drawing_pages

def parse_pdf_with_ai(pdf_path):
    """AI와 Langchain을 사용하여 PDF를 파싱하고 초기 마크다운 파일 생성
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        tuple: (마크다운 파일 경로, 도면 페이지 목록)
    """
    print("Langchain을 사용한 AI 기반 도면 식별 방식 사용 중...")
    
    # AI를 사용한 도면 식별
    drawing_pages = identify_drawing_pages_with_ai(pdf_path)
    
    # PDF의 총 페이지 수 확인
    pdf_document = fitz.open(pdf_path)
    total_pages = len(pdf_document)
    pdf_document.close()
    
    # 일반 페이지 리스트 생성
    regular_pages = [i for i in range(total_pages) if i not in drawing_pages]
    
    # 디렉토리 생성
    temp_dir, output_dir = create_dirs()
    pdf_name = get_pdf_name(pdf_path)
    
    print(f"일반 페이지: {regular_pages}")
    print(f"도면 페이지: {drawing_pages}")
    
    # 모든 페이지 pymupdf4llm으로 변환
    print("모든 페이지 내용 추출 중...")
    full_md_text = pymupdf4llm.to_markdown(pdf_path, write_images=True)
    
    # 페이지 구분자로 분리
    page_separator = re.compile(r'<!--\s*page\s+\d+\s*-->')
    md_pages = page_separator.split(full_md_text)
    
    # 페이지 번호 헤더 제거
    md_pages = [re.sub(r'^#+\s*Page\s+\d+\s*$', '', p, flags=re.MULTILINE).strip() for p in md_pages]
    
    # PDF의 총 페이지 수 확인
    pdf_document = fitz.open(pdf_path)
    total_pages = len(pdf_document)
    pdf_document.close()
    
    # 전체 마크다운 조합 (모든 페이지 포함)
    md_text = ""
    if len(md_pages) > 1:  # 첫 번째 요소는 종종 빈 문자열임
        for i in range(total_pages):
            if i < len(md_pages) - 1:  # 안전 검사
                page_content = md_pages[i + 1]  # +1은 첫 번째 빈 요소를 고려
                md_text += f"<!-- page {i} -->\n\n{page_content}\n\n"
    
    # 초기 마크다운 파일 생성
    output_path = output_dir / f"{pdf_name}.md"
    output_path.write_text(md_text, encoding="utf-8")
    
    # 이미지 파일들을 temp 디렉토리로 이동
    for file in pathlib.Path().glob(f"{pdf_name}*.png"):
        shutil.move(str(file), str(temp_dir / file.name))
    
    return output_path, drawing_pages

def parse_pdf(pdf_path):
    """기존 휴리스틱 기반 PDF 파싱 (하위호환용)"""
    # AI 기반 파서로 대체
    return parse_pdf_with_ai(pdf_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("사용법: python pdf_parser.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = pathlib.Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"오류: 파일 {pdf_path}이(가) 존재하지 않습니다")
        sys.exit(1)
    
    output_path, drawing_pages = parse_pdf(pdf_path)
    print(f"초기 마크다운 생성: {output_path}")
    print(f"도면 페이지: {drawing_pages}")
