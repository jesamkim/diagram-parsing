import pathlib
import os
from pdf2image import convert_from_path
from utils import create_dirs, get_pdf_name, is_rotated_image, correct_rotation, ensure_unique_filename
from config import TEMP_DIR, OUTPUT_DIR, IMAGE_QUALITY, IMAGE_FORMAT

def extract_drawing_pages(pdf_path, page_numbers):
    """PDF에서 도면 페이지를 추출하여 PNG로 변환
    
    Args:
        pdf_path: PDF 파일 경로
        page_numbers: 추출할 페이지 번호 리스트 (0-based)
        
    Returns:
        list: 변환된 이미지 경로와 원본 페이지 번호의 딕셔너리 리스트
              [{'path': '경로', 'page_num': 페이지번호}, ...]
    """
    # 디렉토리 생성
    temp_dir, _ = create_dirs()
    pdf_name = get_pdf_name(pdf_path)
    
    # 페이지 번호가 없으면 빈 리스트 반환
    if not page_numbers:
        print("추출할 도면 페이지가 없습니다.")
        return []
    
    # PDF가 한 페이지만 있는 경우 처리
    if len(page_numbers) == 1 and page_numbers[0] == 0:
        print("PDF 전체가 도면입니다.")
    
    # 특정 페이지 번호를 1-based로 변환 (pdf2image는 1-based 인덱싱 사용)
    page_numbers_1_based = [p + 1 for p in page_numbers]
    
    try:
        # 각 페이지를 개별적으로 변환하여 인덱싱 오류 방지
        image_paths = []
        print(f"도면 페이지를 PNG로 변환 중: {page_numbers_1_based}...")
        
        for i, page_num in enumerate(page_numbers):
            # 각 페이지를 개별적으로 변환 (1-based 페이지 번호 사용)
            page_images = convert_from_path(
                pdf_path,
                dpi=IMAGE_QUALITY,
                fmt=IMAGE_FORMAT.lower(),
                first_page=page_num + 1,  # 0-based에서 1-based로 변환
                last_page=page_num + 1,
                thread_count=4
            )
            
            if not page_images:
                print(f"경고: 페이지 {page_num}을 변환할 수 없습니다.")
                continue
                
            image = page_images[0]  # 한 페이지만 변환했으므로 첫 번째 이미지만 사용
            
            # 이미지 저장 경로
            image_filename = f"{pdf_name}_drawing_page_{page_num}.{IMAGE_FORMAT.lower()}"
            image_path = temp_dir / image_filename
            
            # 중복 파일명 방지
            image_path = ensure_unique_filename(image_path)
            
            # 이미지 저장
            image.save(str(image_path), format=IMAGE_FORMAT)
            print(f"도면 이미지 저장: {image_path}")
            
            # 회전 감지 및 보정
            if is_rotated_image(image_path):
                print(f"회전된 도면 감지: {image_path}")
                corrected_path = temp_dir / f"{image_path.stem}_corrected{image_path.suffix}"
                corrected_path = ensure_unique_filename(corrected_path)
                corrected_img_path = correct_rotation(image_path, str(corrected_path))
                image_paths.append({
                    'path': corrected_img_path,
                    'page_num': page_num
                })
                print(f"회전 보정 완료: {corrected_img_path}")
            else:
                image_paths.append({
                    'path': str(image_path),
                    'page_num': page_num
                })
        
        return image_paths
    
    except Exception as e:
        print(f"도면 페이지 추출 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("사용법: python drawing_extractor.py <pdf_file> [page_numbers]")
        print("page_numbers: JSON 형식의 페이지 번호 리스트, 예: '[0,2,5]'")
        sys.exit(1)
    
    pdf_path = pathlib.Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"오류: 파일 {pdf_path}이(가) 존재하지 않습니다")
        sys.exit(1)
    
    # 페이지 번호 옵션
    if len(sys.argv) > 2:
        try:
            page_numbers = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print(f"오류: 잘못된 페이지 번호 형식: {sys.argv[2]}")
            sys.exit(1)
    else:
        # 첫 페이지만 처리
        page_numbers = [0]
    
    image_paths = extract_drawing_pages(pdf_path, page_numbers)
    print("변환된 도면 이미지:")
    for path in image_paths:
        print(f"  - {path}")
