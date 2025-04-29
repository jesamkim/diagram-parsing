import pathlib
import time
import os
import shutil
import numpy as np
from PIL import Image
from config import TEMP_DIR, OUTPUT_DIR, BASE_WAIT_TIME

def create_dirs():
    """필요한 디렉토리 생성"""
    temp_dir = pathlib.Path(TEMP_DIR)
    temp_dir.mkdir(exist_ok=True)
    
    output_dir = pathlib.Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    
    return temp_dir, output_dir

def get_pdf_name(pdf_path):
    """PDF 파일 이름 추출"""
    return pathlib.Path(pdf_path).stem

def wait_with_backoff(retry_count):
    """지수 백오프를 사용한 대기"""
    wait_time = BASE_WAIT_TIME * (2 ** retry_count)
    time.sleep(wait_time)

def clean_temp_dir():
    """임시 디렉토리 정리"""
    temp_dir = pathlib.Path(TEMP_DIR)
    if temp_dir.exists():
        for file in temp_dir.iterdir():
            if file.is_file():
                file.unlink()

def is_rotated_image(image_path, threshold=10):
    """이미지가 회전되었는지 감지
    
    Args:
        image_path: 이미지 파일 경로
        threshold: 회전 감지 임계값(도)
        
    Returns:
        bool: 이미지가 회전되었는지 여부
    """
    try:
        with Image.open(image_path) as img:
            # 이미지를 numpy 배열로 변환
            img_array = np.array(img.convert('L'))
            
            # 허프 변환 또는 간단한 에지 기반 분석으로 주요 선 각도 분석
            # 여기서는 간단한 구현만 제공
            
            # 실제 구현에서는 좀 더 정교한 방법 사용 필요
            # 예: cv2.HoughLines 등을 사용한 정밀 분석
            
            # 현재는 이미지 크기 기반 휴리스틱 사용
            width, height = img.size
            aspect_ratio = width / height
            
            # 세로로 긴 이미지(가로<세로)이고 종횡비가 특정 값 이하면 회전된 것으로 간주
            if aspect_ratio < 0.8:
                return True
                
            return False
    except Exception as e:
        print(f"회전 감지 중 오류 발생: {str(e)}")
        return False

def correct_rotation(image_path, output_path=None):
    """회전된 이미지 보정
    
    Args:
        image_path: 보정할 이미지 경로
        output_path: 출력 이미지 경로, None이면 원본 경로에 저장
        
    Returns:
        str: 보정된 이미지 경로
    """
    if output_path is None:
        output_path = image_path
        
    try:
        with Image.open(image_path) as img:
            # 이미지가 세로로 길면 90도 회전
            width, height = img.size
            if width < height:
                rotated_img = img.transpose(Image.ROTATE_90)
                rotated_img.save(output_path)
                return output_path
            return image_path
    except Exception as e:
        print(f"이미지 회전 보정 중 오류 발생: {str(e)}")
        return image_path

def ensure_unique_filename(file_path):
    """중복되지 않는 파일 이름 생성
    
    Args:
        file_path: 원본 파일 경로
        
    Returns:
        Path: 중복되지 않는 파일 경로
    """
    path = pathlib.Path(file_path)
    counter = 1
    while path.exists():
        stem = path.stem
        # 이미 카운터가 포함된 경우 제거
        if stem.rfind('-') > 0:
            try:
                base, count = stem.rsplit('-', 1)
                if count.isdigit():
                    stem = base
            except ValueError:
                pass
        new_name = f"{stem}-{counter}{path.suffix}"
        path = path.with_name(new_name)
        counter += 1
    return path

def get_file_size(file_path):
    """파일 크기 조회 (MB)"""
    path = pathlib.Path(file_path)
    if path.exists():
        return path.stat().st_size / (1024 * 1024)
    return 0
