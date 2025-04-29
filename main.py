import sys
import pathlib
import json
import argparse
from pdf_parser import parse_pdf, parse_pdf_with_ai
from drawing_extractor import extract_drawing_pages
from drawing_analyzer import analyze_drawings
from md_generator import generate_markdown
from utils import create_dirs, clean_temp_dir, get_pdf_name

def parse_arguments():
    """명령행 인수 파싱"""
    parser = argparse.ArgumentParser(description='PDF 도면 파싱 및 분석 도구')
    parser.add_argument('pdf_file', help='분석할 PDF 파일 경로')
    parser.add_argument('--clean', action='store_true', help='시작 전 임시 디렉토리 정리')
    parser.add_argument('--skip-analysis', action='store_true', help='도면 분석 단계 건너뛰기')
    parser.add_argument('--skip-claude', action='store_true', help='Claude를 사용한 최종 마크다운 최적화 단계 건너뛰기')
    return parser.parse_args()

def main():
    """메인 워크플로우"""
    # 명령행 인수 파싱
    args = parse_arguments()
    
    # PDF 파일 경로 확인
    pdf_path = pathlib.Path(args.pdf_file)
    if not pdf_path.exists():
        print(f"오류: PDF 파일 {pdf_path}이(가) 존재하지 않습니다.")
        sys.exit(1)
    
    # 임시 디렉토리 정리 (옵션)
    if args.clean:
        print("임시 디렉토리 정리 중...")
        clean_temp_dir()
    
    # 디렉토리 생성
    create_dirs()
    
    try:
        # 1단계: PDF 파싱 및 도면 페이지 식별 (AI 기반)
        print("1단계: PDF 파싱 및 도면 페이지 식별 중...")
        md_path, drawing_pages = parse_pdf_with_ai(pdf_path)
        print(f"  - 마크다운 파일 생성: {md_path}")
        print(f"  - 도면 페이지 식별: {drawing_pages}")
        
        # 2단계: 도면 페이지 PNG 변환
        print("\n2단계: 도면 페이지 PNG 변환 중...")
        if drawing_pages:
            drawing_paths = extract_drawing_pages(pdf_path, drawing_pages)
            print(f"  - 변환된 도면 이미지: {len(drawing_paths)}개")
        else:
            print("  - 도면 페이지가 없습니다.")
            drawing_paths = []
        
        # 3단계: 도면 분석
        print("\n3단계: 도면 분석 수행 중...")
        if drawing_paths and not args.skip_analysis:
            drawing_results = analyze_drawings(drawing_paths, md_path)  # 페이지 번호는 이미 drawing_paths에 포함
            print(f"  - 도면 분석 완료: {len(drawing_results)}개")
            
            # 분석 결과 저장 (디버깅용)
            results_path = pathlib.Path(f"{get_pdf_name(pdf_path)}_drawing_analysis.json")
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(drawing_results, f, ensure_ascii=False, indent=2)
        else:
            if args.skip_analysis:
                print("  - 도면 분석 단계 건너뛰기 (--skip-analysis 옵션)")
            else:
                print("  - 분석할 도면이 없습니다.")
            drawing_results = []
        
        # 4단계: 최종 마크다운 생성
        print("\n4단계: 최종 마크다운 생성 중...")
        output_path = generate_markdown(md_path, drawing_results)
        print(f"  - 최종 마크다운 파일: {output_path}")
        
        print("\n처리 완료!")
        print(f"결과 파일: {output_path}")
        return 0
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
